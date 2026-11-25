// Command resolve answers "which declaration does this call bind to" for Go files with the
// official go/types checker. It needs no network and no module downloads: packages of the
// repository are type-checked from source, the standard library through the default
// importer, and anything else is an empty fake package, so type errors are tolerated.
//
// Request on stdin, response on stdout, both JSON (see review_core.intel.resolvers).
package main

import (
	"encoding/json"
	"go/ast"
	"go/build"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type site struct {
	Path   string `json:"path"`
	Line   int    `json:"line"`
	Column int    `json:"column"`
	Name   string `json:"name"`
}

type target struct {
	Path string `json:"path"`
	Line int    `json:"line"`
	Name string `json:"name"`
	Key  string `json:"key"`
}

type resolved struct {
	Path    string   `json:"path"`
	Line    int      `json:"line"`
	Column  int      `json:"column"`
	Targets  []target `json:"targets"`
	External bool     `json:"external"`
}

type request struct {
	Root  string   `json:"root"`
	Files []string `json:"files"`
	Sites []site   `json:"sites"`
}

type response struct {
	Sites      []resolved `json:"sites"`
	TypeErrors int        `json:"type_errors"`
	Errors     []string   `json:"errors"`
}

type module struct{ path, dir string }

type checker struct {
	root     string
	fset     *token.FileSet
	modules  []module
	packages map[string]*types.Package
	std      types.Importer
	errors   int
	info     *types.Info
}

func main() {
	var req request
	if err := json.NewDecoder(os.Stdin).Decode(&req); err != nil {
		fail(err)
	}
	c := &checker{
		root:     req.Root,
		fset:     token.NewFileSet(),
		packages: map[string]*types.Package{},
		info:     &types.Info{Uses: map[*ast.Ident]types.Object{}},
	}
	c.std = importer.Default()
	c.modules = findModules(req.Root)
	out := response{Sites: []resolved{}, Errors: []string{}}
	byFile := map[string][]site{}
	for _, s := range req.Sites {
		byFile[s.Path] = append(byFile[s.Path], s)
	}
	dirs := map[string]bool{}
	for _, f := range req.Files {
		dirs[filepath.Dir(f)] = true
	}
	parsed := map[string]*ast.File{}
	for dir := range dirs {
		for name, files := range c.groups(dir) {
			_ = name
			c.check(dir, files, parsed)
		}
	}
	for _, f := range req.Files {
		file := parsed[f]
		if file == nil {
			out.Errors = append(out.Errors, "not type-checked: "+f)
			continue
		}
		out.Sites = append(out.Sites, c.resolve(f, file, byFile[f])...)
	}
	out.TypeErrors = c.errors
	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil {
		fail(err)
	}
}

func fail(err error) {
	os.Stderr.WriteString(err.Error() + "\n")
	os.Exit(2)
}

func findModules(root string) []module {
	var mods []module
	filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() || d.Name() != "go.mod" {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return nil
		}
		for _, line := range strings.Split(string(data), "\n") {
			fields := strings.Fields(line)
			if len(fields) >= 2 && fields[0] == "module" {
				mods = append(mods, module{strings.Trim(fields[1], "\""), filepath.Dir(path)})
				break
			}
		}
		return nil
	})
	// Longest module path first, so nested modules win.
	sort.Slice(mods, func(i, j int) bool { return len(mods[i].path) > len(mods[j].path) })
	return mods
}

// groups returns the Go files of one directory by package clause, honouring build tags.
func (c *checker) groups(rel string) map[string][]string {
	dir := filepath.Join(c.root, rel)
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil
	}
	groups := map[string][]string{}
	ctx := build.Default
	for _, e := range entries {
		name := e.Name()
		if e.IsDir() || !strings.HasSuffix(name, ".go") {
			continue
		}
		if ok, _ := ctx.MatchFile(dir, name); !ok {
			continue
		}
		file, err := parser.ParseFile(token.NewFileSet(), filepath.Join(dir, name), nil, parser.PackageClauseOnly)
		if err != nil {
			continue
		}
		groups[file.Name.Name] = append(groups[file.Name.Name], filepath.Join(rel, name))
	}
	return groups
}

func (c *checker) parse(rel string) *ast.File {
	file, _ := parser.ParseFile(c.fset, filepath.Join(c.root, rel), nil, parser.SkipObjectResolution)
	return file
}

func (c *checker) config() *types.Config {
	return &types.Config{
		Importer:    importerFunc(c.importPackage),
		Error:       func(error) { c.errors++ },
		FakeImportC: true,
	}
}

// check type-checks one package of the requested files, tests included, recording uses.
func (c *checker) check(dir string, files []string, parsed map[string]*ast.File) {
	var asts []*ast.File
	for _, f := range files {
		if file := c.parse(f); file != nil {
			parsed[f] = file
			asts = append(asts, file)
		}
	}
	if len(asts) == 0 {
		return
	}
	c.config().Check(c.importPath(dir), c.fset, asts, c.info)
}

func (c *checker) importPath(rel string) string {
	abs := filepath.Join(c.root, rel)
	for _, m := range c.modules {
		if r, err := filepath.Rel(m.dir, abs); err == nil && !strings.HasPrefix(r, "..") {
			if r == "." {
				return m.path
			}
			return m.path + "/" + filepath.ToSlash(r)
		}
	}
	return filepath.ToSlash(rel)
}

type importerFunc func(path string) (*types.Package, error)

func (f importerFunc) Import(path string) (*types.Package, error) { return f(path) }

// importPackage type-checks repository packages from source (non-test files only).
func (c *checker) importPackage(path string) (*types.Package, error) {
	if pkg, ok := c.packages[path]; ok {
		return pkg, nil
	}
	for _, m := range c.modules {
		var dir string
		if vendored := filepath.Join(m.dir, "vendor", path); isDir(vendored) {
			dir = vendored
		} else if path == m.path {
			dir = m.dir
		} else if strings.HasPrefix(path, m.path+"/") {
			dir = filepath.Join(m.dir, strings.TrimPrefix(path, m.path+"/"))
		} else {
			continue
		}
		if !isDir(dir) {
			break
		}
		rel, _ := filepath.Rel(c.root, dir)
		placeholder := types.NewPackage(path, filepath.Base(path))
		c.packages[path] = placeholder // breaks import cycles
		var asts []*ast.File
		for name, files := range c.groups(rel) {
			if strings.HasSuffix(name, "_test") {
				continue
			}
			for _, f := range files {
				if strings.HasSuffix(f, "_test.go") {
					continue
				}
				if file := c.parse(f); file != nil {
					asts = append(asts, file)
				}
			}
		}
		pkg, _ := c.config().Check(path, c.fset, asts, c.info)
		if pkg != nil {
			c.packages[path] = pkg
			return pkg, nil
		}
		return placeholder, nil
	}
	if pkg, err := c.std.Import(path); err == nil {
		c.packages[path] = pkg
		return pkg, nil
	}
	fake := types.NewPackage(path, filepath.Base(path))
	fake.MarkComplete()
	c.packages[path] = fake
	return fake, nil
}

func isDir(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

func (c *checker) resolve(rel string, file *ast.File, sites []site) []resolved {
	type key struct{ line, col int }
	calls := map[key]*ast.CallExpr{}
	byLine := map[int][]*ast.CallExpr{}
	ast.Inspect(file, func(n ast.Node) bool {
		if call, ok := n.(*ast.CallExpr); ok {
			p := c.fset.Position(call.Pos())
			calls[key{p.Line, p.Column}] = call
			byLine[p.Line] = append(byLine[p.Line], call)
		}
		return true
	})
	var out []resolved
	for _, s := range sites {
		call := calls[key{s.Line, s.Column + 1}]
		if call == nil {
			for _, candidate := range byLine[s.Line] {
				if id := callee(candidate.Fun); id != nil && id.Name == s.Name {
					call = candidate
					break
				}
			}
		}
		r := resolved{Path: s.Path, Line: s.Line, Column: s.Column, Targets: []target{}}
		if call != nil {
			if id := callee(call.Fun); id != nil {
				if fn, ok := c.info.Uses[id].(*types.Func); ok && fn.Pos().IsValid() {
					p := c.fset.Position(fn.Pos())
					if path, err := filepath.Rel(c.root, p.Filename); err == nil && !strings.HasPrefix(path, "..") {
						path = filepath.ToSlash(path)
						r.Targets = append(r.Targets, target{path, p.Line, fn.Name(), path + ":" + itoa(p.Line)})
					} else {
						r.External = true
					}
				}
			}
		}
		out = append(out, r)
	}
	return out
}

func callee(expr ast.Expr) *ast.Ident {
	for {
		switch e := expr.(type) {
		case *ast.ParenExpr:
			expr = e.X
		case *ast.IndexExpr:
			expr = e.X
		case *ast.IndexListExpr:
			expr = e.X
		case *ast.Ident:
			return e
		case *ast.SelectorExpr:
			return e.Sel
		default:
			return nil
		}
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var digits []byte
	for n > 0 {
		digits = append([]byte{byte('0' + n%10)}, digits...)
		n /= 10
	}
	return string(digits)
}
