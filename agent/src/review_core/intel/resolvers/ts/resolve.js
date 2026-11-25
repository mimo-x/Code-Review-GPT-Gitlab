// Resolves TypeScript/JavaScript call sites to declarations with the official TypeScript
// compiler API (type checker). No node_modules are needed: missing packages type as any and
// their calls stay unresolved, while calls between repository files bind precisely.
// Request on stdin, response on stdout, JSON (see review_core.intel.resolvers).
"use strict";
const fs = require("fs");
const path = require("path");
const ts = require(process.env.REVIEW_CORE_TYPESCRIPT || "typescript");

function readRequest() {
  return JSON.parse(fs.readFileSync(0, "utf8"));
}

function options(root, files) {
  // Nearest tsconfig above the first requested file, else the repository root one.
  let dir = path.dirname(path.join(root, files[0] || "x"));
  let config;
  while (dir.startsWith(root)) {
    const candidate = path.join(dir, "tsconfig.json");
    if (fs.existsSync(candidate)) { config = candidate; break; }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  let base = {};
  if (config) {
    const read = ts.readConfigFile(config, ts.sys.readFile);
    if (!read.error) {
      base = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(config)).options;
    }
  }
  return Object.assign({}, base, {
    allowJs: true, checkJs: false, noEmit: true, skipLibCheck: true, types: [],
    maxNodeModuleJsDepth: 0, jsx: base.jsx || ts.JsxEmit.Preserve,
    moduleResolution: base.moduleResolution || ts.ModuleResolutionKind.Bundler,
    module: base.module || ts.ModuleKind.ESNext, target: base.target || ts.ScriptTarget.ESNext,
    allowImportingTsExtensions: true, resolveJsonModule: true, noLib: false,
  });
}

function calleeName(expression) {
  let e = expression;
  while (e && (ts.isParenthesizedExpression(e) || ts.isNonNullExpression(e) || ts.isAsExpression(e))) e = e.expression;
  if (!e) return undefined;
  if (ts.isIdentifier(e)) return e;
  if (ts.isPropertyAccessExpression(e)) return e.name;
  if (ts.isElementAccessExpression(e) && ts.isStringLiteral(e.argumentExpression)) return e.argumentExpression;
  return undefined;
}

function main() {
  const request = readRequest();
  const root = path.resolve(request.root);
  const files = request.files.map((f) => path.join(root, f));
  const program = ts.createProgram({ rootNames: files, options: options(root, request.files) });
  const checker = program.getTypeChecker();
  const out = { sites: [], definitions: [], errors: [] };
  const byFile = new Map();
  for (const site of request.sites) {
    if (!byFile.has(site.path)) byFile.set(site.path, []);
    byFile.get(site.path).push(site);
  }
  for (const [rel, sites] of byFile) {
    const sf = program.getSourceFile(path.join(root, rel));
    if (!sf) {
      out.errors.push("not in program: " + rel);
      for (const s of sites) out.sites.push({ path: s.path, line: s.line, column: s.column, targets: [] });
      continue;
    }
    const calls = new Map();
    const visit = (node) => {
      if (ts.isCallExpression(node) || ts.isNewExpression(node) || ts.isDecorator(node)) {
        const start = sf.getLineAndCharacterOfPosition(node.getStart(sf));
        const key = (start.line + 1) + ":" + start.character;
        if (!calls.has(key)) calls.set(key, []);
        calls.get(key).push(node);
        const byLine = "line:" + (start.line + 1);
        if (!calls.has(byLine)) calls.set(byLine, []);
        calls.get(byLine).push(node);
      }
      ts.forEachChild(node, visit);
    };
    visit(sf);
    for (const s of sites) {
      const result = { path: s.path, line: s.line, column: s.column, targets: [], external: false };
      let candidates = calls.get(s.line + ":" + s.column) || [];
      const pick = (nodes) => nodes.find((n) => {
        const id = calleeName(n.expression);
        return id && id.text === s.name;
      });
      let node = pick(candidates) || pick(calls.get("line:" + s.line) || []);
      if (node) {
        const id = calleeName(node.expression);
        let symbol = id && checker.getSymbolAtLocation(id);
        if (symbol && symbol.flags & ts.SymbolFlags.Alias) {
          try { symbol = checker.getAliasedSymbol(symbol); } catch (e) { /* keep alias */ }
        }
        for (const decl of (symbol && symbol.declarations) || []) {
          const file = decl.getSourceFile();
          const target = path.relative(root, file.fileName);
          if (program.isSourceFileDefaultLibrary(file) || target.startsWith("..") || target.split(path.sep).includes("node_modules")) {
            result.external = true;
            continue;
          }
          const line = file.getLineAndCharacterOfPosition(decl.getStart(file)).line + 1;
          let name = decl.name && decl.name.getText ? decl.name.getText(file) : undefined;
          if (!name && ts.getCombinedModifierFlags && (ts.getCombinedModifierFlags(decl) & ts.ModifierFlags.Default)) name = "default";
          if (!name && ts.isExportAssignment && ts.isExportAssignment(decl)) name = "default";
          if (!name && (ts.isConstructorDeclaration(decl))) name = "constructor";
          name = name || s.name;
          const rel2 = target.split(path.sep).join("/");
          result.targets.push({ path: rel2, line, name, key: rel2 + ":" + line });
        }
        if (result.targets.length) result.external = false;
      }
      out.sites.push(result);
    }
  }
  process.stdout.write(JSON.stringify(out));
}

main();
