// Resolves Java call sites to their declarations with Spoon in noclasspath mode: missing
// dependencies leave references unresolved instead of failing the build of the model.
// Request on stdin, response on stdout, JSON (see review_core.intel.resolvers).

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.code.CtAbstractInvocation;
import spoon.reflect.cu.SourcePosition;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtExecutable;
import spoon.reflect.reference.CtExecutableReference;
import spoon.reflect.visitor.filter.TypeFilter;

public class Resolve {
    public static void main(String[] args) throws Exception {
        ObjectMapper json = new ObjectMapper();
        JsonNode request = json.readTree(System.in);
        Path root = Path.of(request.get("root").asText()).toAbsolutePath().normalize();
        Launcher launcher = new Launcher();
        launcher.getEnvironment().setNoClasspath(true);
        launcher.getEnvironment().setComplianceLevel(21);
        launcher.getEnvironment().setCommentEnabled(false);
        launcher.getEnvironment().setIgnoreDuplicateDeclarations(true);
        launcher.getEnvironment().setIgnoreSyntaxErrors(true);
        launcher.getEnvironment().setLevel("OFF");
        for (JsonNode file : request.get("files")) {
            File source = root.resolve(file.asText()).toFile();
            if (source.isFile()) {
                launcher.addInputResource(source.getPath());
            }
        }
        ObjectNode response = json.createObjectNode();
        ArrayNode sites = response.putArray("sites");
        ArrayNode errors = response.putArray("errors");
        response.putArray("definitions");
        CtModel model;
        try {
            model = launcher.buildModel();
        } catch (Exception e) {
            errors.add("model build failed: " + e.getClass().getSimpleName());
            json.writeValue(System.out, response);
            return;
        }
        // Index invocations by file and line; a site matches by line and called name.
        Map<String, List<CtAbstractInvocation<?>>> byLine = new HashMap<>();
        for (CtElement element : model.getElements(new TypeFilter<>(CtAbstractInvocation.class))) {
            SourcePosition position = element.getPosition();
            if (!position.isValidPosition() || position.getFile() == null) {
                continue;
            }
            String path = relative(root, position.getFile());
            if (path == null) {
                continue;
            }
            byLine.computeIfAbsent(path + ":" + position.getLine(), k -> new ArrayList<>())
                .add((CtAbstractInvocation<?>) element);
        }
        for (JsonNode site : request.get("sites")) {
            String path = site.get("path").asText();
            int line = site.get("line").asInt();
            String name = site.get("name").asText();
            ObjectNode out = sites.addObject();
            out.put("path", path);
            out.put("line", line);
            out.put("column", site.get("column").asInt());
            ArrayNode targets = out.putArray("targets");
            for (CtAbstractInvocation<?> invocation :
                    byLine.getOrDefault(path + ":" + line, List.of())) {
                CtExecutableReference<?> reference = invocation.getExecutable();
                if (reference == null) {
                    continue;
                }
                String simple = reference.isConstructor()
                    ? reference.getDeclaringType() == null ? "" : reference.getDeclaringType().getSimpleName()
                    : reference.getSimpleName();
                if (!simple.equals(name)) {
                    continue;
                }
                CtExecutable<?> declaration;
                try {
                    declaration = reference.getExecutableDeclaration();
                } catch (Exception e) {
                    declaration = null;
                }
                if (declaration == null || !declaration.getPosition().isValidPosition()) {
                    continue;
                }
                String target = relative(root, declaration.getPosition().getFile());
                if (target == null) {
                    continue;
                }
                int targetLine = declaration.getPosition().getLine();
                ObjectNode t = targets.addObject();
                t.put("path", target);
                t.put("line", targetLine);
                t.put("name", simple);
                t.put("key", target + ":" + targetLine);
                break;
            }
        }
        json.writeValue(System.out, response);
    }

    private static String relative(Path root, File file) {
        if (file == null) {
            return null;
        }
        Path path = file.toPath().toAbsolutePath().normalize();
        if (!path.startsWith(root)) {
            return null;
        }
        return root.relativize(path).toString().replace(File.separatorChar, '/');
    }
}
