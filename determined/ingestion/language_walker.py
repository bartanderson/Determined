"""
LanguageWalker: multi-language symbol and edge extraction via ast-grep (tree-sitter backend).

Phase 1: JS/TS
Phase 2: Go     (implement before Go corpus ingestion)
Phase 3: Rust   (implement before Rust corpus ingestion)

All downstream RMs import from this module, not from ast-grep directly.
Swapping the backend touches only this file.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    from ast_grep_py import SgRoot
    _AST_GREP_AVAILABLE = True
except ImportError:
    _AST_GREP_AVAILABLE = False

# JS/TS built-ins to filter from callee lists
_JS_BUILTINS = frozenset({
    "console", "Math", "Object", "Array", "Promise", "JSON", "String",
    "Number", "Boolean", "Date", "RegExp", "Error", "Map", "Set",
    "parseInt", "parseFloat", "isNaN", "isFinite", "encodeURIComponent",
    "decodeURIComponent", "setTimeout", "clearTimeout", "setInterval",
    "clearInterval", "fetch", "document", "window", "navigator",
    "localStorage", "sessionStorage", "Symbol", "Proxy", "Reflect",
    "WeakMap", "WeakSet", "WeakRef", "globalThis", "undefined", "null",
})

# Go built-in packages / identifiers to filter
_GO_BUILTINS = frozenset({
    # stdlib packages
    "fmt", "os", "io", "log", "sync", "math", "sort", "strings",
    "strconv", "errors", "context", "time", "http", "json", "bytes",
    "bufio", "path", "filepath", "runtime", "reflect",
    # builtin functions
    "make", "len", "cap", "append", "copy", "delete", "close",
    "panic", "recover", "print", "println", "new", "real", "imag",
    "complex", "min", "max",
    # primitive types used in type-cast expressions: string(x), int(x), etc.
    "string", "int", "int8", "int16", "int32", "int64",
    "uint", "uint8", "uint16", "uint32", "uint64", "uintptr",
    "float32", "float64", "complex64", "complex128", "bool", "byte", "rune",
    "error",
})


# CUDA runtime / math builtins to filter from callees
_CUDA_BUILTINS = frozenset({
    # CUDA runtime API
    "cudaMalloc", "cudaFree", "cudaMemcpy", "cudaMemset", "cudaMemcpyAsync",
    "cudaDeviceSynchronize", "cudaGetLastError", "cudaCheckError",
    "cudaGetDeviceCount", "cudaSetDevice", "cudaGetDeviceProperties",
    "cudaStreamCreate", "cudaStreamDestroy", "cudaStreamSynchronize",
    "cudaEventCreate", "cudaEventDestroy", "cudaEventRecord", "cudaEventSynchronize",
    "cudaEventElapsedTime", "cudaFuncSetAttribute",
    # cuBLAS
    "cublasCreate", "cublasDestroy", "cublasSgemm", "cublasSgemmEx",
    "cublasSetMathMode",
    # Thread/block intrinsics
    "blockIdx", "blockDim", "threadIdx", "gridDim", "warpSize",
    "__syncthreads", "__syncwarp", "__threadfence", "__threadfence_block",
    # Atomic operations
    "atomicAdd", "atomicSub", "atomicMax", "atomicMin", "atomicCAS",
    "atomicExch", "atomicAnd", "atomicOr", "atomicXor",
    # CUDA math
    "sqrtf", "rsqrtf", "expf", "logf", "powf", "fabsf", "fmaxf", "fminf",
    "floorf", "ceilf", "roundf", "tanhf", "sinf", "cosf", "__expf",
    "__fmaf_rn", "__float2int_rn", "__int2float_rn",
    # Warp shuffle
    "__shfl_sync", "__shfl_down_sync", "__shfl_up_sync", "__shfl_xor_sync",
    "__ballot_sync", "__any_sync", "__all_sync",
    # Memory
    "__ldg", "__stcs", "make_float2", "make_float4", "make_int2", "make_int4",
})

# Regex for CUDA kernel launches: name<<<grid, block>>>(args)
_CUDA_KERNEL_LAUNCH_RE = re.compile(r'\b(\w+)\s*<<<[^>]*>>>\s*\(')

# CUDA qualifier keywords
_CUDA_QUALIFIERS = frozenset({"__global__", "__device__", "__host__"})

# Languages that need a different tree-sitter backend than their logical name
_TS_LANGUAGE_MAP = {"cuda": "cpp"}

# C standard library functions to filter from callees
_C_BUILTINS = frozenset({
    # stdio
    "printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf",
    "fopen", "fclose", "fread", "fwrite", "fgets", "fputs", "feof", "ferror",
    "fflush", "fseek", "ftell", "rewind", "fgetc", "fputc", "getc", "putc",
    "getchar", "putchar", "puts", "gets", "perror",
    # stdlib
    "malloc", "calloc", "realloc", "free", "exit", "abort", "atexit",
    "atoi", "atof", "atol", "atoll", "strtol", "strtod", "strtoul",
    "qsort", "bsearch", "rand", "srand", "abs", "labs",
    "getenv", "setenv", "system",
    # string
    "strlen", "strcpy", "strncpy", "strcat", "strncat", "strcmp", "strncmp",
    "strchr", "strrchr", "strstr", "strtok", "strdup",
    "memcpy", "memmove", "memset", "memcmp", "memchr",
    # math
    "sqrt", "pow", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "log", "log2", "log10", "exp", "ceil", "floor", "fabs", "fmod", "round",
    # assert / POSIX basics
    "assert", "open", "close", "read", "write", "stat", "mkdir", "unlink",
})

# Rust built-in types, traits, macros, and std identifiers to filter from callees
_RUST_BUILTINS = frozenset({
    # macros (called with !)
    "println", "print", "eprintln", "eprint", "format", "vec", "assert",
    "assert_eq", "assert_ne", "panic", "todo", "unimplemented", "unreachable",
    "dbg", "write", "writeln",
    # common std methods / traits that appear as bare identifiers
    "unwrap", "expect", "ok", "err", "map", "and_then", "or_else",
    "is_some", "is_none", "is_ok", "is_err", "clone", "into", "from",
    "iter", "collect", "len", "push", "pop", "contains", "get", "insert",
    "remove", "default", "new", "drop", "to_string", "to_owned",
    "copied", "cloned", "as_ref", "as_mut", "borrow", "borrow_mut",
    "iter_mut", "keys", "values", "entry",
    # enum variants and special identifiers
    "Some", "None", "Ok", "Err", "Self", "super",
    # common iterator adaptors that appear as method calls
    "filter", "map", "flat_map", "for_each", "any", "all", "find",
    "count", "sum", "product", "zip", "enumerate", "take", "skip",
    "chain", "peekable", "rev", "sorted",
    # primitive types
    "bool", "i8", "i16", "i32", "i64", "i128", "isize",
    "u8", "u16", "u32", "u64", "u128", "usize", "f32", "f64",
    "char", "str", "String", "Vec", "Option", "Result", "Box",
    "Rc", "Arc", "Cell", "RefCell",
})


@dataclass
class LangSpec:
    """Per-language config for the shared call-edge walk.

    To add a new language: fill in a LangSpec and register it in _lang_spec().
    The walk loop in _shared_call_edges handles the rest — no new walk code needed.

    callee_extractor: maps a call_expression's function node to a callee string.
    builtins: set of base names to filter from the callee list.
    fn_ranges_builder: zero-arg callable (bound method) that returns fn_ranges.
    compute_resolved: if True, cross-file symbol lookup sets resolved=True when callee
                      matches a symbol defined in this file (JS only for now).
    """
    callee_extractor: Callable
    builtins: frozenset
    fn_ranges_builder: Callable
    compute_resolved: bool = False


class LanguageWalker:
    """
    Single abstraction for symbol and edge extraction across languages.

    language: string passed to SgRoot — 'javascript', 'typescript', 'go', 'rust', etc.
              For .jsx/.tsx files pass 'jsx' or 'tsx'.
    """

    def __init__(self, src: str, file_path: str, language: str):
        if not _AST_GREP_AVAILABLE:
            raise RuntimeError("ast-grep-py not installed. Run: pip install ast-grep-py")
        self._src = src
        self._lines = src.splitlines()
        self._file_path = file_path
        self._language = language
        ts_lang = _TS_LANGUAGE_MAP.get(language, language)
        self._root = SgRoot(src, ts_lang)
        self._basename = os.path.splitext(os.path.basename(file_path))[0]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def symbols(self) -> list[dict]:
        """Return list of dicts suitable for inserting into the functions table."""
        lang = self._language
        if lang in ("javascript", "typescript", "jsx", "tsx"):
            return self._js_symbols()
        if lang == "go":
            return self._go_symbols()
        if lang == "rust":
            return self._rust_symbols()
        if lang == "c":
            return self._c_symbols()
        if lang == "cuda":
            return self._cuda_symbols()
        return []

    def call_edges(self) -> list[tuple]:
        """
        Return list of (caller_fqdn, callee_name, 'static', resolved: bool).
        resolved is False at this stage; cross-file resolution happens in persist layer.
        """
        lang = self._language
        if lang not in ("javascript", "typescript", "jsx", "tsx", "go", "rust", "c", "cuda"):
            return []
        edges = self._shared_call_edges(self._lang_spec())
        if lang == "cuda":
            edges.extend(self._cuda_kernel_launches())
        return edges

    def _lang_spec(self) -> LangSpec:
        """Return the LangSpec for self._language. Called only for supported languages."""
        lang = self._language
        if lang in ("javascript", "typescript", "jsx", "tsx"):
            return LangSpec(
                callee_extractor=self._js_callee_name,
                builtins=_JS_BUILTINS,
                fn_ranges_builder=self._js_fn_ranges,
                compute_resolved=True,
            )
        if lang == "go":
            return LangSpec(
                callee_extractor=self._go_callee_name,
                builtins=_GO_BUILTINS,
                fn_ranges_builder=self._go_fn_ranges,
            )
        if lang == "rust":
            return LangSpec(
                callee_extractor=self._rust_callee_name,
                builtins=_RUST_BUILTINS,
                fn_ranges_builder=self._rust_fn_ranges,
            )
        if lang == "c":
            return LangSpec(
                callee_extractor=self._c_callee_name,
                builtins=_C_BUILTINS,
                fn_ranges_builder=self._c_fn_ranges,
            )
        if lang == "cuda":
            return LangSpec(
                callee_extractor=self._cuda_callee_name,
                builtins=_CUDA_BUILTINS | _C_BUILTINS,
                fn_ranges_builder=self._cuda_fn_ranges,
            )
        raise ValueError(f"No LangSpec for language: {lang}")

    def _shared_call_edges(self, spec: LangSpec) -> list[tuple]:
        """
        Unified call-edge walk used by all languages.

        Callee name extraction, builtins filter, and fn-range attribution are
        all delegated to the LangSpec so this loop never borrows another
        language's extractor (the root cause of the Go and Rust silent-drop bugs).
        """
        results = []
        root = self._root.root()
        fn_ranges = spec.fn_ranges_builder()
        symbol_names = {s["name"] for s in self.symbols()} if spec.compute_resolved else set()

        # For TypeScript: populate type map and fn_ranges cache so _js_callee_name
        # can resolve typed receivers (obj.method() → TypeName.method()).
        if self._language in ("typescript", "tsx"):
            self._type_map = self._ts_type_map()
            self._fn_ranges_cache = fn_ranges
        else:
            self._type_map = {}
            self._fn_ranges_cache = []

        try:
            for call in root.find_all({"rule": {"kind": "call_expression"}}):
                caller_fqdn = self._enclosing_fqdn(call, fn_ranges)
                if caller_fqdn is None:
                    continue
                func_node = call.field("function")
                if func_node is None:
                    continue
                callee = spec.callee_extractor(func_node)
                if callee is None:
                    continue
                # Split on both separators so JS 'obj.m', Go 'pkg.Fn', Rust 'Mod::Fn' all work
                base = callee.split("::")[0].split(".")[0]
                if base in spec.builtins:
                    continue
                if callee == caller_fqdn:
                    continue
                resolved = callee in symbol_names if spec.compute_resolved else False
                results.append((caller_fqdn, callee, "static", resolved))
        finally:
            self._type_map = {}
            self._fn_ranges_cache = []

        return results

    def data_flow_edges(self) -> list[tuple]:
        """
        Return list of (caller_fqdn, callee_fqdn, 'data_flow', provenance: str).
        Provenance tags mirror the Python side for unified querying:
          data_flow_arg, data_flow_var, data_flow_for_iter, data_flow_var_kwarg
        """
        lang = self._language
        if lang in ("javascript", "typescript", "jsx", "tsx"):
            return self._js_data_flow()
        if lang == "go":
            return self._go_data_flow()
        if lang == "rust":
            return self._rust_data_flow()
        return []

    # ------------------------------------------------------------------
    # JS/TS: symbols
    # ------------------------------------------------------------------

    def _js_symbols(self) -> list[dict]:
        results = []
        root = self._root.root()

        # Named function declarations: function foo(...) { }
        for node in root.find_all({"rule": {"kind": "function_declaration"}}):
            name_node = node.field("name")
            if name_node is None:
                continue
            name = name_node.text()
            fqdn = f"{self._basename}.{name}"
            results.append(self._make_symbol(
                fqdn, node, is_stub=self._js_is_stub(node),
                return_type=self._ts_return_type(node),
                param_types_json=self._ts_param_types(node),
                docstring=self._preceding_comment(node),
            ))

        # Arrow functions and function expressions assigned to variables:
        # const foo = (...) => { } / const foo = function(...) { }
        for node in root.find_all({"rule": {"kind": "lexical_declaration"}}):
            for decl in node.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = decl.field("name")
                val_node = decl.field("value")
                if id_node is None or val_node is None:
                    continue
                if val_node.kind() not in ("arrow_function", "function_expression"):
                    continue
                name = id_node.text()
                fqdn = f"{self._basename}.{name}"
                results.append(self._make_symbol(
                    fqdn, decl, is_stub=self._js_is_stub(val_node),
                    return_type=self._ts_return_type(val_node),
                    param_types_json=self._ts_param_types(val_node),
                    docstring=self._preceding_comment(node),
                ))

        # Class method definitions
        for cls_node in root.find_all({"rule": {"kind": "class_declaration"}}):
            cls_name_node = cls_node.field("name")
            cls_name = cls_name_node.text() if cls_name_node else self._basename
            body = cls_node.field("body")
            if body is None:
                continue
            for method in body.find_all({"rule": {"kind": "method_definition"}}):
                name_node = method.field("name")
                if name_node is None:
                    continue
                method_name = name_node.text()
                fqdn = f"{cls_name}.{method_name}"
                results.append(self._make_symbol(
                    fqdn, method, is_stub=self._js_is_stub(method),
                    return_type=self._ts_return_type(method),
                    param_types_json=self._ts_param_types(method),
                    docstring=self._preceding_comment(method),
                ))

        # Object literal methods assigned to const/let/var (common in JS modules)
        for node in root.find_all({"rule": {"kind": "lexical_declaration"}}):
            for decl in node.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = decl.field("name")
                val_node = decl.field("value")
                if id_node is None or val_node is None:
                    continue
                if val_node.kind() != "object":
                    continue
                obj_name = id_node.text()
                for pair in val_node.find_all({"rule": {"kind": "pair"}}):
                    key_node = pair.field("key")
                    val = pair.field("value")
                    if key_node is None or val is None:
                        continue
                    if val.kind() not in ("arrow_function", "function_expression"):
                        continue
                    method_name = key_node.text().strip('"\'')
                    fqdn = f"{obj_name}.{method_name}"
                    results.append(self._make_symbol(fqdn, pair, is_stub=self._js_is_stub(val)))

        return results

    # ------------------------------------------------------------------
    # TypeScript: type annotation helpers
    # ------------------------------------------------------------------

    def _ts_return_type(self, fn_node) -> str | None:
        """Extract the return type string from a function/method node's type_annotation field."""
        if self._language not in ("typescript", "tsx"):
            return None
        ta = fn_node.field("return_type")
        if ta is None:
            return None
        # type_annotation text is ": SomeType" — strip leading ": "
        text = ta.text().lstrip(": ").strip()
        return text if text else None

    def _ts_param_types(self, fn_node) -> str | None:
        """Extract parameter types from a function/method node's formal_parameters field.
        Returns JSON list of {"name": str, "type": str} or None if no typed params found."""
        if self._language not in ("typescript", "tsx"):
            return None
        params_node = fn_node.field("parameters")
        if params_node is None:
            return None
        result = []
        for param in params_node.find_all({"rule": {"kind": "required_parameter"}}):
            pattern = param.field("pattern")
            type_ann = param.field("type")
            name = pattern.text() if pattern else ""
            if not name:
                continue
            type_str = None
            if type_ann is not None:
                type_str = type_ann.text().lstrip(": ").strip() or None
            result.append({"name": name, "type": type_str})
        if not result:
            return None
        import json as _json
        return _json.dumps(result)

    def _ts_type_map(self) -> dict[str, str]:
        """Build {var_name: TypeName} for TypeScript files from type annotations and new-expressions.
        Used by _js_callee_name to resolve obj.method() → TypeName.method()."""
        if self._language not in ("typescript", "tsx"):
            return {}
        root = self._root.root()
        type_map: dict[str, str] = {}

        for ld in root.find_all({"rule": {"kind": "lexical_declaration"}}):
            for decl in ld.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = decl.field("name")
                if id_node is None:
                    continue
                var_name = id_node.text()

                # Explicit type annotation: const x: MyClass = ...
                type_ann = decl.field("type")
                if type_ann is not None:
                    type_text = type_ann.text().lstrip(": ").strip()
                    # For generics like Array<Item>, use outer type name only
                    outer = type_text.split("<")[0].strip()
                    if outer:
                        type_map[var_name] = outer
                        continue

                # new-expression initializer: const x = new MyClass(...)
                val = decl.field("value")
                if val is not None and val.kind() == "new_expression":
                    ctor = val.field("constructor")
                    if ctor is not None:
                        type_map[var_name] = ctor.text()

        # Class field declarations: private repo: UserRepository
        for cls_node in root.find_all({"rule": {"kind": "class_declaration"}}):
            body = cls_node.field("body")
            if body is None:
                continue
            for field_def in body.find_all({"rule": {"kind": "public_field_definition"}}):
                prop = field_def.field("name")
                type_ann = field_def.field("type")
                if prop is not None and type_ann is not None:
                    type_text = type_ann.text().lstrip(": ").strip()
                    outer = type_text.split("<")[0].strip()
                    if outer:
                        # Store as both "repo" and "this.repo"
                        type_map[prop.text()] = outer
                        type_map[f"this.{prop.text()}"] = outer

        # Function/method parameters with type annotations
        for fn_node in root.find_all({"rule": {"kind": "function_declaration"}}):
            params = fn_node.field("parameters")
            if params:
                for param in params.find_all({"rule": {"kind": "required_parameter"}}):
                    pattern = param.field("pattern")
                    type_ann = param.field("type")
                    if pattern and type_ann:
                        type_text = type_ann.text().lstrip(": ").strip()
                        outer = type_text.split("<")[0].strip()
                        if outer and outer not in ("string", "number", "boolean", "any", "void", "never", "unknown", "object"):
                            type_map[pattern.text()] = outer

        for cls_node in root.find_all({"rule": {"kind": "class_declaration"}}):
            body = cls_node.field("body")
            if body is None:
                continue
            for method in body.find_all({"rule": {"kind": "method_definition"}}):
                params = method.field("parameters")
                if params:
                    for param in params.find_all({"rule": {"kind": "required_parameter"}}):
                        pattern = param.field("pattern")
                        type_ann = param.field("type")
                        if pattern and type_ann:
                            type_text = type_ann.text().lstrip(": ").strip()
                            outer = type_text.split("<")[0].strip()
                            if outer and outer not in ("string", "number", "boolean", "any", "void", "never", "unknown", "object"):
                                type_map[pattern.text()] = outer

        return type_map

    def _preceding_comment(self, node) -> str | None:
        """Return the doc comment immediately above node, or None.

        Handles:
          Python   -- triple-quoted strings handled by parse_ast; not needed here.
          Go       -- consecutive `//` lines directly above the declaration.
          Rust     -- consecutive `///` lines directly above the declaration.
          JS/TS    -- /** ... */ block ending on the line before the declaration.
        """
        start_line = node.range().start.line  # 0-indexed
        if start_line == 0:
            return None
        lines = self._lines
        lang = self._language

        if lang in ("go", "c"):
            # Check for /* ... */ block comment ending immediately above
            end_idx = start_line - 1
            while end_idx >= 0 and not lines[end_idx].strip():
                end_idx -= 1
            if end_idx >= 0 and lines[end_idx].strip().endswith("*/"):
                i = end_idx
                while i >= 0 and "/*" not in lines[i]:
                    i -= 1
                if i >= 0:
                    block = lines[i:end_idx + 1]
                    parts = []
                    for bl in block:
                        s = bl.strip().lstrip("/*").lstrip("*").strip()
                        if s:
                            parts.append(s)
                    if parts:
                        return " ".join(parts)
            # Walk backwards collecting `//` lines
            collected = []
            i = start_line - 1
            while i >= 0 and lines[i].strip().startswith("//"):
                collected.append(lines[i].strip().lstrip("/").strip())
                i -= 1
            if collected:
                return " ".join(reversed(collected))

        if lang == "rust":
            # Walk backwards collecting `///` lines
            collected = []
            i = start_line - 1
            while i >= 0 and lines[i].strip().startswith("///"):
                collected.append(lines[i].strip().lstrip("/").strip())
                i -= 1
            if collected:
                return " ".join(reversed(collected))

        if lang in ("javascript", "typescript", "jsx", "tsx"):
            # Look for a /** ... */ block ending on start_line - 1
            end_idx = start_line - 1
            # skip blank lines between comment and declaration
            while end_idx >= 0 and not lines[end_idx].strip():
                end_idx -= 1
            if end_idx >= 0 and lines[end_idx].strip().endswith("*/"):
                # find opening /**
                i = end_idx
                while i >= 0 and "/**" not in lines[i]:
                    i -= 1
                if i >= 0:
                    block = lines[i:end_idx + 1]
                    # strip * prefixes and collect non-empty lines
                    parts = []
                    for l in block:
                        s = l.strip().lstrip("/*").lstrip("*").strip()
                        if s:
                            parts.append(s)
                    if parts:
                        return " ".join(parts)

        return None

    def _make_symbol(self, fqdn: str, node, is_stub: bool = False,
                     return_type: str | None = None,
                     param_types_json: str | None = None,
                     docstring: str | None = None) -> dict:
        return {
            "file_path": self._file_path,
            "name": fqdn,
            "line_number": node.range().start.line + 1,
            "return_type": return_type,
            "arguments_json": "[]",
            "param_types_json": param_types_json,
            "docstring": docstring,
            "is_stub": is_stub,
            "decorators_json": None,
            "http_route": None,
        }

    def _js_is_stub(self, node) -> bool:
        """A function is a stub if its body contains only a throw, return, or is empty."""
        body = node.field("body")
        if body is None:
            return True
        text = body.text().strip()
        if text in ("{}", "{ }"):
            return True
        # Single-statement bodies that are just throw or return undefined
        inner = text.lstrip("{").rstrip("}").strip()
        if inner.startswith("throw ") or inner == "return;" or inner == "":
            return True
        return False

    # ------------------------------------------------------------------
    # JS/TS: call edges
    # ------------------------------------------------------------------

    def _js_fn_ranges(self) -> list[tuple]:
        """
        Return list of (start_line, end_line, fqdn) for every function scope.
        Used to attribute call expressions to their enclosing function.
        """
        ranges = []
        root = self._root.root()

        def _add(fqdn, node):
            r = node.range()
            ranges.append((r.start.line, r.end.line, fqdn))

        for node in root.find_all({"rule": {"kind": "function_declaration"}}):
            name_node = node.field("name")
            if name_node:
                _add(f"{self._basename}.{name_node.text()}", node)

        for node in root.find_all({"rule": {"kind": "lexical_declaration"}}):
            for decl in node.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = decl.field("name")
                val_node = decl.field("value")
                if id_node and val_node and val_node.kind() in ("arrow_function", "function_expression"):
                    _add(f"{self._basename}.{id_node.text()}", val_node)

        for cls_node in root.find_all({"rule": {"kind": "class_declaration"}}):
            cls_name_node = cls_node.field("name")
            cls_name = cls_name_node.text() if cls_name_node else self._basename
            body = cls_node.field("body")
            if body:
                for method in body.find_all({"rule": {"kind": "method_definition"}}):
                    name_node = method.field("name")
                    if name_node:
                        _add(f"{cls_name}.{name_node.text()}", method)

        # Object literal methods: const obj = { method: function() {} }
        for node in root.find_all({"rule": {"kind": "lexical_declaration"}}):
            for decl in node.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = decl.field("name")
                val_node = decl.field("value")
                if id_node is None or val_node is None or val_node.kind() != "object":
                    continue
                obj_name = id_node.text()
                for pair in val_node.find_all({"rule": {"kind": "pair"}}):
                    key_node = pair.field("key")
                    val = pair.field("value")
                    if key_node and val and val.kind() in ("arrow_function", "function_expression"):
                        _add(f"{obj_name}.{key_node.text().strip(chr(39) + chr(34))}", val)

        # Sort by start line so _enclosing_fqdn can find the tightest enclosing scope
        ranges.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        return ranges

    def _enclosing_fqdn(self, node, fn_ranges: list[tuple]) -> str | None:
        """Return the fqdn of the tightest function scope enclosing the node."""
        line = node.range().start.line
        # Find all scopes containing this line, pick the tightest (largest start)
        candidates = [
            (start, end, fqdn)
            for start, end, fqdn in fn_ranges
            if start <= line <= end
        ]
        if not candidates:
            return None
        # Tightest = largest start line
        return max(candidates, key=lambda x: x[0])[2]

    def enclosing_fqdn_by_line(self, line: int, fn_ranges: list[tuple]) -> str | None:
        """Return the fqdn of the tightest function scope containing the given 0-based line."""
        candidates = [
            (start, end, fqdn)
            for start, end, fqdn in fn_ranges
            if start <= line <= end
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[0])[2]

    def js_fn_ranges(self) -> list[tuple]:
        """Public accessor for JS function ranges, for use by external extractors."""
        return self._js_fn_ranges()

    def _js_callee_name(self, func_node) -> str | None:
        """Extract callee name from the function field of a call_expression.
        For TypeScript files, resolves typed receivers: obj.method() → TypeName.method()."""
        kind = func_node.kind()
        if kind == "identifier":
            t = func_node.text()
            return t if "\n" not in t and len(t) < 120 else None
        if kind == "member_expression":
            obj = func_node.field("object")
            prop = func_node.field("property")
            if obj is None or prop is None:
                return None
            obj_text = obj.text()
            prop_text = prop.text()
            # Resolve "this.field.method()" chains: obj is a member_expression itself
            if obj.kind() == "member_expression":
                inner_obj = obj.field("object")
                inner_prop = obj.field("property")
                if inner_obj and inner_prop and inner_obj.text() == "this":
                    type_map = getattr(self, "_type_map", {})
                    field_key = f"this.{inner_prop.text()}"
                    resolved = type_map.get(field_key)
                    if resolved:
                        return f"{resolved}.{prop_text}"
            # Resolve simple receiver: obj.method() → TypeName.method()
            type_map = getattr(self, "_type_map", {})
            if obj_text == "this":
                # Resolve this.method() → ClassName.method() via enclosing class
                fn_ranges = getattr(self, "_fn_ranges_cache", [])
                if fn_ranges:
                    line = func_node.range().start.line
                    enclosing = self.enclosing_fqdn_by_line(line, fn_ranges)
                    if enclosing and "." in enclosing:
                        cls_name = enclosing.split(".")[0]
                        return f"{cls_name}.{prop_text}"
            resolved_type = type_map.get(obj_text)
            if resolved_type:
                return f"{resolved_type}.{prop_text}"
            return f"{obj_text}.{prop_text}"
        return None

    # ------------------------------------------------------------------
    # JS/TS: data flow edges
    # ------------------------------------------------------------------

    def _go_data_flow(self) -> list[tuple]:
        """
        Emit data_flow edges for Go:
          L1: fnB(fnA())         -> data_flow_arg
          L2: x := fnA(); fnB(x) -> data_flow_var
        """
        results = []
        fn_ranges = self._go_fn_ranges()
        root = self._root.root()
        fn_bindings: dict[str, dict[str, str]] = {}

        # --- L1: nested call args ---
        for call in root.find_all({"rule": {"kind": "call_expression"}}):
            outer_fqdn = self._enclosing_fqdn(call, fn_ranges)
            if outer_fqdn is None:
                continue
            func_node = call.field("function")
            if func_node is None:
                continue
            outer_callee = self._go_callee_name(func_node)
            if outer_callee is None:
                continue
            args = call.field("arguments")
            if args is None:
                continue
            for arg in args.find_all({"rule": {"kind": "call_expression"}}):
                inner_func = arg.field("function")
                if inner_func is None:
                    continue
                inner_callee = self._go_callee_name(inner_func)
                if inner_callee:
                    results.append((outer_fqdn, inner_callee, "data_flow", "data_flow_arg"))

        # --- L2: x := fnA(); fnB(x) ---
        # short_var_declaration: "x := fnA()"
        for decl in root.find_all({"rule": {"kind": "short_var_declaration"}}):
            outer_fqdn = self._enclosing_fqdn(decl, fn_ranges)
            if outer_fqdn is None:
                continue
            # left = expression_list of identifiers, right = expression_list of values
            left = decl.field("left")
            right = decl.field("right")
            if left is None or right is None:
                continue
            # right may be a single call_expression
            if right.kind() == "call_expression":
                fn_node = right.field("function")
                if fn_node is None:
                    continue
                callee = self._go_callee_name(fn_node)
                if callee:
                    var_name = left.text().split(",")[0].strip()
                    fn_bindings.setdefault(outer_fqdn, {})[var_name] = callee
            else:
                # expression_list — walk children
                for child in right.find_all({"rule": {"kind": "call_expression"}}):
                    fn_node = child.field("function")
                    if fn_node is None:
                        continue
                    callee = self._go_callee_name(fn_node)
                    if callee:
                        var_name = left.text().split(",")[0].strip()
                        fn_bindings.setdefault(outer_fqdn, {})[var_name] = callee

        # Emit L2 edges
        for call in root.find_all({"rule": {"kind": "call_expression"}}):
            outer_fqdn = self._enclosing_fqdn(call, fn_ranges)
            if outer_fqdn is None:
                continue
            bindings = fn_bindings.get(outer_fqdn, {})
            if not bindings:
                continue
            func_node = call.field("function")
            if func_node is None:
                continue
            outer_callee = self._go_callee_name(func_node)
            if outer_callee is None:
                continue
            args = call.field("arguments")
            if args is None:
                continue
            for arg in args.children():
                if arg.kind() == "identifier" and arg.text() in bindings:
                    results.append((outer_fqdn, bindings[arg.text()], "data_flow", "data_flow_var"))

        return results

    def _rust_data_flow(self) -> list[tuple]:
        """
        Emit data_flow edges for Rust:
          L1: fnB(fnA())          -> data_flow_arg
          L2: let x = fnA(); fnB(x) -> data_flow_var
        """
        results = []
        fn_ranges = self._rust_fn_ranges()
        root = self._root.root()
        fn_bindings: dict[str, dict[str, str]] = {}

        def _rust_callee(call_node) -> str | None:
            """Extract callee name from a Rust call_expression."""
            func = call_node.field("function")
            if func is None:
                return None
            kind = func.kind()
            if kind == "identifier":
                return func.text()
            if kind == "scoped_identifier":
                return func.text()  # e.g. "Vec::new"
            if kind == "field_expression":
                field = func.field("field")
                value = func.field("value")
                if field and value and value.kind() == "identifier":
                    return f"{value.text()}.{field.text()}"
            return None

        # --- L1: nested call args ---
        for call in root.find_all({"rule": {"kind": "call_expression"}}):
            outer_fqdn = self._enclosing_fqdn(call, fn_ranges)
            if outer_fqdn is None:
                continue
            outer_callee = _rust_callee(call)
            if outer_callee is None:
                continue
            args = call.field("arguments")
            if args is None:
                continue
            for arg in args.find_all({"rule": {"kind": "call_expression"}}):
                inner_callee = _rust_callee(arg)
                if inner_callee:
                    results.append((outer_fqdn, inner_callee, "data_flow", "data_flow_arg"))

        # --- L2: let x = fnA(); fnB(x) ---
        for let_decl in root.find_all({"rule": {"kind": "let_declaration"}}):
            outer_fqdn = self._enclosing_fqdn(let_decl, fn_ranges)
            if outer_fqdn is None:
                continue
            value = let_decl.field("value")
            if value is None or value.kind() != "call_expression":
                continue
            callee = _rust_callee(value)
            if callee is None:
                continue
            pattern = let_decl.field("pattern")
            if pattern is None:
                continue
            var_name = pattern.text()
            fn_bindings.setdefault(outer_fqdn, {})[var_name] = callee

        # Emit L2 edges
        for call in root.find_all({"rule": {"kind": "call_expression"}}):
            outer_fqdn = self._enclosing_fqdn(call, fn_ranges)
            if outer_fqdn is None:
                continue
            bindings = fn_bindings.get(outer_fqdn, {})
            if not bindings:
                continue
            outer_callee = _rust_callee(call)
            if outer_callee is None:
                continue
            args = call.field("arguments")
            if args is None:
                continue
            for arg in args.children():
                if arg.kind() == "identifier" and arg.text() in bindings:
                    results.append((outer_fqdn, bindings[arg.text()], "data_flow", "data_flow_var"))

        return results

    def _js_data_flow(self) -> list[tuple]:
        """
        Emit data_flow edges for:
          L1: fnB(fnA())  -> data_flow_arg
          L2: const x = fnA(); fnB(x)  -> data_flow_var
          L3a: for (const x of fnA())  -> data_flow_for_iter
          L3b: fnB({key: x}) where x is bound  -> data_flow_var_kwarg
        """
        results = []
        fn_ranges = self._js_fn_ranges()
        root = self._root.root()

        # Per-function binding maps: line_range -> {var_name: callee_fqdn}
        # We'll build them lazily per enclosing function
        fn_bindings: dict[str, dict[str, str]] = {}

        # --- L1: nested call args ---
        for call in root.find_all({"rule": {"kind": "call_expression"}}):
            outer_fqdn = self._enclosing_fqdn(call, fn_ranges)
            if outer_fqdn is None:
                continue
            func_node = call.field("function")
            if func_node is None:
                continue
            outer_callee = self._js_callee_name(func_node)
            if outer_callee is None or outer_callee.split(".")[0] in _JS_BUILTINS:
                continue
            args = call.field("arguments")
            if args is None:
                continue
            for arg in args.find_all({"rule": {"kind": "call_expression"}}):
                inner_func = arg.field("function")
                if inner_func is None:
                    continue
                inner_callee = self._js_callee_name(inner_func)
                if inner_callee and inner_callee.split(".")[0] not in _JS_BUILTINS:
                    results.append((outer_fqdn, inner_callee, "data_flow", "data_flow_arg"))

        # --- L2: const/let x = fnA(); ... fnB(x) ---
        # Build bindings per function scope from variable declarations
        for decl in root.find_all({"rule": {"kind": "variable_declaration"}}):
            outer_fqdn = self._enclosing_fqdn(decl, fn_ranges)
            if outer_fqdn is None:
                continue
            for declarator in decl.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = declarator.field("name")
                val_node = declarator.field("value")
                if id_node is None or val_node is None:
                    continue
                if val_node.kind() != "call_expression":
                    continue
                fn_node = val_node.field("function")
                if fn_node is None:
                    continue
                callee = self._js_callee_name(fn_node)
                if callee and callee.split(".")[0] not in _JS_BUILTINS:
                    fn_bindings.setdefault(outer_fqdn, {})[id_node.text()] = callee

        # Also handle lexical_declaration (const/let at statement level)
        for decl in root.find_all({"rule": {"kind": "lexical_declaration"}}):
            outer_fqdn = self._enclosing_fqdn(decl, fn_ranges)
            if outer_fqdn is None:
                continue
            for declarator in decl.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = declarator.field("name")
                val_node = declarator.field("value")
                if id_node is None or val_node is None:
                    continue
                if val_node.kind() != "call_expression":
                    continue
                fn_node = val_node.field("function")
                if fn_node is None:
                    continue
                callee = self._js_callee_name(fn_node)
                if callee and callee.split(".")[0] not in _JS_BUILTINS:
                    fn_bindings.setdefault(outer_fqdn, {})[id_node.text()] = callee

        # Emit L2 edges: when a bound variable appears as an argument
        for call in root.find_all({"rule": {"kind": "call_expression"}}):
            outer_fqdn = self._enclosing_fqdn(call, fn_ranges)
            if outer_fqdn is None:
                continue
            bindings = fn_bindings.get(outer_fqdn, {})
            if not bindings:
                continue
            func_node = call.field("function")
            if func_node is None:
                continue
            outer_callee = self._js_callee_name(func_node)
            if outer_callee is None or outer_callee.split(".")[0] in _JS_BUILTINS:
                continue
            args = call.field("arguments")
            if args is None:
                continue
            for arg in args.children():
                if arg.kind() == "identifier" and arg.text() in bindings:
                    src_callee = bindings[arg.text()]
                    results.append((outer_fqdn, src_callee, "data_flow", "data_flow_var"))

        # --- L3a: for (const x of fnA()) ---
        # tree-sitter uses for_in_statement for both for-in and for-of; filter by operator
        for for_node in root.find_all({"rule": {"kind": "for_in_statement"}}):
            outer_fqdn = self._enclosing_fqdn(for_node, fn_ranges)
            if outer_fqdn is None:
                continue
            op = for_node.field("operator")
            if op is None or op.text() != "of":
                continue
            right = for_node.field("right")
            if right is None or right.kind() != "call_expression":
                continue
            fn_node = right.field("function")
            if fn_node is None:
                continue
            callee = self._js_callee_name(fn_node)
            if callee and callee.split(".")[0] not in _JS_BUILTINS:
                results.append((outer_fqdn, callee, "data_flow", "data_flow_for_iter"))
                # Bind loop variable
                left = for_node.field("left")
                if left:
                    var_name = self._js_for_var_name(left)
                    if var_name:
                        fn_bindings.setdefault(outer_fqdn, {})[var_name] = callee

        # --- L3b: fnB({key: x}) where x is bound (object arg with bound identifier values) ---
        for call in root.find_all({"rule": {"kind": "call_expression"}}):
            outer_fqdn = self._enclosing_fqdn(call, fn_ranges)
            if outer_fqdn is None:
                continue
            bindings = fn_bindings.get(outer_fqdn, {})
            if not bindings:
                continue
            func_node = call.field("function")
            if func_node is None:
                continue
            outer_callee = self._js_callee_name(func_node)
            if outer_callee is None or outer_callee.split(".")[0] in _JS_BUILTINS:
                continue
            args = call.field("arguments")
            if args is None:
                continue
            for arg in args.children():
                if arg.kind() != "object":
                    continue
                for pair in arg.find_all({"rule": {"kind": "pair"}}):
                    val = pair.field("value")
                    if val and val.kind() == "identifier" and val.text() in bindings:
                        src_callee = bindings[val.text()]
                        results.append((outer_fqdn, src_callee, "data_flow", "data_flow_var_kwarg"))

        return results

    def response_consumers(self) -> list[tuple]:
        """
        Return list of (fn_fqdn, keys: list[str]) for JS/TS functions that
        consume JSON responses. Detects:
          const {key, key2} = await resp.json()
          const {key} = data   (where data is from .json() or .then)
          data.key             (property access on a response variable)
        """
        lang = self._language
        if lang not in ("javascript", "typescript", "jsx", "tsx"):
            return []
        return self._js_response_consumers()

    def _js_response_consumers(self) -> list[tuple]:
        """
        Detect JS/TS patterns that destructure or access keys from a JSON response.
        Returns [(fn_fqdn, [key, ...]), ...] — one entry per function.
        """
        results = []
        fn_ranges = self._js_fn_ranges()
        root = self._root.root()

        # Collect per-function consumed keys
        fn_keys: dict[str, set[str]] = {}

        # Pattern 1: object destructuring from .json() call
        # const {key1, key2} = await resp.json()  or  const {key1} = data.json()
        for decl in root.find_all({"rule": {"kind": "lexical_declaration"}}):
            outer_fqdn = self._enclosing_fqdn(decl, fn_ranges)
            if outer_fqdn is None:
                continue
            for declarator in decl.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = declarator.field("name")
                val_node = declarator.field("value")
                if id_node is None or val_node is None:
                    continue
                # Look for object_pattern on the left side (destructuring)
                if id_node.kind() != "object_pattern":
                    continue
                # Check that the right side involves .json() somewhere
                val_text = val_node.text()
                if ".json()" not in val_text:
                    continue
                # Extract keys from the destructuring pattern
                for shorthand in id_node.find_all({"rule": {"kind": "shorthand_property_identifier_pattern"}}):
                    fn_keys.setdefault(outer_fqdn, set()).add(shorthand.text())
                for pair in id_node.find_all({"rule": {"kind": "pair_pattern"}}):
                    key_node = pair.field("key")
                    if key_node:
                        fn_keys.setdefault(outer_fqdn, set()).add(key_node.text())

        # Pattern 2: property access on a variable bound from .json() or fetch response
        # data.key  /  response.data.key  — track which vars come from .json()
        json_vars: dict[str, set[str]] = {}  # fn_fqdn -> set of var names holding .json() result

        for decl in root.find_all({"rule": {"kind": "lexical_declaration"}}):
            outer_fqdn = self._enclosing_fqdn(decl, fn_ranges)
            if outer_fqdn is None:
                continue
            for declarator in decl.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = declarator.field("name")
                val_node = declarator.field("value")
                if id_node is None or val_node is None:
                    continue
                if id_node.kind() != "identifier":
                    continue
                if ".json()" in val_node.text():
                    json_vars.setdefault(outer_fqdn, set()).add(id_node.text())

        for call in root.find_all({"rule": {"kind": "member_expression"}}):
            outer_fqdn = self._enclosing_fqdn(call, fn_ranges)
            if outer_fqdn is None:
                continue
            obj = call.field("object")
            prop = call.field("property")
            if obj is None or prop is None:
                continue
            var_name = obj.text().split(".")[0]
            if var_name in json_vars.get(outer_fqdn, set()):
                key = prop.text()
                if key and key.isidentifier() and key not in ("json", "then", "catch", "finally"):
                    fn_keys.setdefault(outer_fqdn, set()).add(key)

        for fqdn, keys in fn_keys.items():
            if keys:
                results.append((fqdn, sorted(keys)))

        return results

    def _js_for_var_name(self, left_node) -> str | None:
        """Extract the loop variable name from a for-of left side."""
        kind = left_node.kind()
        if kind == "identifier":
            return left_node.text()
        # lexical_declaration: const x / let x
        if kind in ("lexical_declaration", "variable_declaration"):
            for decl in left_node.find_all({"rule": {"kind": "variable_declarator"}}):
                id_node = decl.field("name")
                if id_node:
                    return id_node.text()
        return None

    # ------------------------------------------------------------------
    # C: symbols, call edges (Phase 4)
    # ------------------------------------------------------------------

    def _c_fn_declarator(self, node):
        """Walk the declarator chain to find a function_declarator and its name.

        Handles:
          int foo(...)           -> declarator = function_declarator
          int *foo(...)          -> declarator = pointer_declarator -> function_declarator
          static int foo(...)    -> same as above (storage class is a separate child)

        Returns (name: str, fn_decl_node) or (None, None) if not a function.
        """
        decl = node.field("declarator")
        if decl is None:
            return None, None
        # Unwrap pointer_declarator chains (for pointer return types like int *foo(...))
        while decl is not None and decl.kind() in ("pointer_declarator", "abstract_pointer_declarator"):
            decl = decl.field("declarator")
        if decl is None or decl.kind() != "function_declarator":
            return None, None
        name_node = decl.field("declarator")
        if name_node is None or name_node.kind() != "identifier":
            return None, None
        return name_node.text(), decl

    def _c_is_stub(self, node) -> bool:
        """A C function definition is a stub if its body is empty or trivially sentinel."""
        body = node.field("body")
        if body is None:
            return True
        text = body.text().strip()
        if text in ("{}", "{ }"):
            return True
        inner = text.lstrip("{").rstrip("}").strip()
        if not inner:
            return True
        # Single trivial sentinel return: return; / return 0; / return NULL;
        import re as _re
        if _re.match(r'^return\s*(0+|NULL|nullptr|false)?\s*;$', inner):
            return True
        return False

    def _c_symbols(self) -> list[dict]:
        results = []
        root = self._root.root()

        # function_definition: full function with body (primarily .c files)
        for node in root.find_all({"rule": {"kind": "function_definition"}}):
            name, _ = self._c_fn_declarator(node)
            if name is None:
                continue
            fqdn = f"{self._basename}::{name}"
            results.append(self._make_symbol(
                fqdn, node,
                is_stub=self._c_is_stub(node),
                docstring=self._preceding_comment(node),
            ))

        # declaration with function_declarator: forward declaration = stub
        # (.h files and forward decls in .c files)
        for node in root.find_all({"rule": {"kind": "declaration"}}):
            name, _ = self._c_fn_declarator(node)
            if name is None:
                continue
            fqdn = f"{self._basename}::{name}"
            results.append(self._make_symbol(
                fqdn, node,
                is_stub=True,
                docstring=self._preceding_comment(node),
            ))

        return results

    def _c_fn_ranges(self) -> list[tuple]:
        ranges = []
        root = self._root.root()
        for node in root.find_all({"rule": {"kind": "function_definition"}}):
            name, _ = self._c_fn_declarator(node)
            if name:
                r = node.range()
                ranges.append((r.start.line, r.end.line, f"{self._basename}::{name}"))
        ranges.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        return ranges

    def _c_callee_name(self, func_node) -> str | None:
        """Extract callee name from a C call_expression function field.

        Patterns:
          identifier          -> bare name: foo(x)
          field_expression    -> struct/pointer access: obj.m(x) or obj->m(x)
          parenthesized_expr  -> function pointer call (*fp)(x) -- skip
        """
        kind = func_node.kind()
        if kind == "identifier":
            return func_node.text()
        if kind == "field_expression":
            arg = func_node.field("argument")
            field = func_node.field("field")
            if arg is None or field is None:
                return None
            if arg.kind() == "identifier":
                return f"{arg.text()}.{field.text()}"
            # Complex receiver (cast, chain) — emit method name only
            return field.text()
        # Function pointer calls and other complex expressions: skip
        return None

    # ------------------------------------------------------------------
    # CUDA: symbols, call edges (Phase 5)
    # ------------------------------------------------------------------

    def _cuda_qualifier(self, node) -> str | None:
        """Return the CUDA qualifier (__global__, __device__, __host__) for a function, if any.

        Checks the type field first (catches single qualifier), then falls back to
        scanning the full function text (catches __host__ __device__ combos).
        """
        type_node = node.field("type")
        if type_node is not None:
            t = type_node.text()
            if t in _CUDA_QUALIFIERS:
                return t
        # Fallback: scan the raw text for any CUDA qualifier
        text = node.text()
        for q in ("__global__", "__device__", "__host__"):
            if q in text:
                return q
        return None

    def _cuda_is_stub(self, node) -> bool:
        body = node.field("body")
        if body is None:
            return True
        text = body.text().strip()
        if text in ("{}", "{ }"):
            return True
        inner = text.lstrip("{").rstrip("}").strip()
        if not inner:
            return True
        if re.match(r'^return\s*(0+|NULL|nullptr|false)?\s*;$', inner):
            return True
        return False

    def _cuda_symbols(self) -> list[dict]:
        results = []
        root = self._root.root()

        for node in root.find_all({"rule": {"kind": "function_definition"}}):
            name, _ = self._c_fn_declarator(node)
            if name is None:
                continue
            fqdn = f"{self._basename}::{name}"
            qualifier = self._cuda_qualifier(node)
            decorators = [qualifier] if qualifier else None
            results.append({
                **self._make_symbol(
                    fqdn, node,
                    is_stub=self._cuda_is_stub(node),
                    docstring=self._preceding_comment(node),
                ),
                "decorators_json": json.dumps(decorators) if decorators else None,
                "is_tool": 1 if qualifier == "__global__" else 0,
            })

        # Forward declarations from headers
        for node in root.find_all({"rule": {"kind": "declaration"}}):
            name, _ = self._c_fn_declarator(node)
            if name is None:
                continue
            fqdn = f"{self._basename}::{name}"
            results.append(self._make_symbol(fqdn, node, is_stub=True,
                                             docstring=self._preceding_comment(node)))

        return results

    def _cuda_fn_ranges(self) -> list[tuple]:
        ranges = []
        root = self._root.root()
        for node in root.find_all({"rule": {"kind": "function_definition"}}):
            name, _ = self._c_fn_declarator(node)
            if name:
                r = node.range()
                ranges.append((r.start.line, r.end.line, f"{self._basename}::{name}"))
        ranges.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        return ranges

    def _cuda_callee_name(self, func_node) -> str | None:
        return self._c_callee_name(func_node)

    def _cuda_kernel_launches(self) -> list[tuple]:
        """Emit call edges for CUDA kernel launches: name<<<grid, block>>>(args)."""
        fn_ranges = self._cuda_fn_ranges()
        results = []
        for m in _CUDA_KERNEL_LAUNCH_RE.finditer(self._src):
            kernel_name = m.group(1)
            # Find line number (0-based) of this match
            line = self._src[:m.start()].count("\n")
            caller = self._enclosing_fqdn_by_line(line, fn_ranges)
            if caller is None:
                continue
            results.append((caller, kernel_name, "static", False))
        return results

    def _enclosing_fqdn_by_line(self, line: int, fn_ranges: list[tuple]) -> str | None:
        candidates = [
            (start, end, fqdn)
            for start, end, fqdn in fn_ranges
            if start <= line <= end
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[0])[2]

    # ------------------------------------------------------------------
    # Go: interface types
    # ------------------------------------------------------------------

    def interface_types(self) -> dict[str, list[str]]:
        """Return {interface_name: [method_name, ...]} for Go files; empty for other languages."""
        if self._language != "go":
            return {}
        return self._go_interface_types()

    def trait_types(self) -> dict[str, list[str]]:
        """Return {trait_name: [method_name, ...]} for Rust files; empty for other languages."""
        if self._language != "rust":
            return {}
        return self._rust_trait_types()

    def impl_trait_map(self) -> dict[str, list[str]]:
        """Return {concrete_type: [trait_name, ...]} for Rust 'impl Trait for Type' blocks."""
        if self._language != "rust":
            return {}
        return self._rust_impl_trait_map()

    def _rust_trait_types(self) -> dict[str, list[str]]:
        """Extract Rust trait definitions: trait Foo { fn method1(...); fn method2(...) }"""
        result: dict[str, list[str]] = {}
        root = self._root.root()
        for trait_node in root.find_all({"rule": {"kind": "trait_item"}}):
            name_node = trait_node.field("name")
            body = trait_node.field("body")
            if name_node is None or body is None:
                continue
            trait_name = name_node.text()
            methods: list[str] = []
            for fn_node in body.find_all({"rule": {"kind": "function_item"}}):
                m_name = fn_node.field("name")
                if m_name is not None:
                    methods.append(m_name.text())
            # Also capture function signatures (fn_signature_item) — trait method declarations
            for fn_node in body.find_all({"rule": {"kind": "function_signature_item"}}):
                m_name = fn_node.field("name")
                if m_name is not None and m_name.text() not in methods:
                    methods.append(m_name.text())
            if methods:
                result[trait_name] = methods
        return result

    def _rust_impl_trait_map(self) -> dict[str, list[str]]:
        """Return {concrete_type: [trait_name, ...]} for all 'impl Trait for Type' blocks."""
        result: dict[str, list[str]] = {}
        root = self._root.root()
        for impl_node in root.find_all({"rule": {"kind": "impl_item"}}):
            trait_node = impl_node.field("trait")
            type_node = impl_node.field("type")
            if trait_node is None or type_node is None:
                continue
            # trait field text may be "TraitName" or "path::TraitName" — use the last segment
            trait_text = trait_node.text().split("::")[-1]
            concrete_type = type_node.text()
            result.setdefault(concrete_type, [])
            if trait_text not in result[concrete_type]:
                result[concrete_type].append(trait_text)
        return result

    def _go_interface_types(self) -> dict[str, list[str]]:
        """Extract Go interface definitions: type X interface { Method1(...) ... }"""
        result: dict[str, list[str]] = {}
        root = self._root.root()
        for type_decl in root.find_all({"rule": {"kind": "type_declaration"}}):
            for spec in type_decl.find_all({"rule": {"kind": "type_spec"}}):
                name_node = spec.field("name")
                type_node = spec.field("type")
                if name_node is None or type_node is None:
                    continue
                if type_node.kind() != "interface_type":
                    continue
                iface_name = name_node.text()
                methods: list[str] = []
                for method in type_node.find_all({"rule": {"kind": "method_elem"}}):
                    m_name = method.field("name")
                    if m_name is not None:
                        methods.append(m_name.text())
                if methods:
                    result[iface_name] = methods
        return result

    # ------------------------------------------------------------------
    # Go: symbols (Phase 2 — stub)
    # ------------------------------------------------------------------

    def _go_symbols(self) -> list[dict]:
        results = []
        root = self._root.root()
        package = self._go_package_name()

        # Top-level functions: func FuncName(...) ...
        for node in root.find_all({"rule": {"kind": "function_declaration"}}):
            name_node = node.field("name")
            if name_node is None:
                continue
            name = name_node.text()
            fqdn = f"{package}.{name}"
            results.append(self._make_symbol(fqdn, node,
                param_types_json=self._go_param_types(node),
                docstring=self._preceding_comment(node)))

        # Method declarations: func (r ReceiverType) MethodName(...) ...
        for node in root.find_all({"rule": {"kind": "method_declaration"}}):
            name_node = node.field("name")
            receiver = node.field("receiver")
            if name_node is None:
                continue
            receiver_type = self._go_receiver_type(receiver) if receiver else package
            method_name = name_node.text()
            fqdn = f"{receiver_type}.{method_name}"
            results.append(self._make_symbol(fqdn, node,
                param_types_json=self._go_param_types(node),
                docstring=self._preceding_comment(node)))

        return results

    def _go_package_name(self) -> str:
        root = self._root.root()
        for node in root.find_all({"rule": {"kind": "package_clause"}}):
            pkg = node.find({"rule": {"kind": "package_identifier"}})
            if pkg:
                return pkg.text()
        return self._basename

    def _go_receiver_type(self, receiver_node) -> str:
        """Extract the type name from a Go method receiver."""
        text = receiver_node.text().strip("()")
        # "(r *TypeName)" or "(r TypeName)"
        parts = text.split()
        for part in reversed(parts):
            clean = part.lstrip("*").strip(")")
            if clean and clean[0].isupper():
                return clean
        return self._basename

    def _go_param_types(self, fn_node) -> str | None:
        """Extract parameter types from a Go function/method node.
        Returns JSON list of {"name": str, "type": str} or None if no typed params.
        For method_declaration nodes the receiver is prepended as the first entry."""
        import json as _json
        result = []

        # Receiver: func (r *TypeName) Method(...) — present on method_declaration nodes only
        receiver_node = fn_node.field("receiver")
        if receiver_node is not None:
            text = receiver_node.text().strip("()")
            parts = text.split()
            if len(parts) >= 2:
                recv_name = parts[0]
                recv_type = parts[-1].lstrip("*")
                if recv_type and recv_type[0].isupper():
                    result.append({"name": recv_name, "type": recv_type})

        params_node = fn_node.field("parameters")
        if params_node is None:
            return _json.dumps(result) if result else None
        for param in params_node.find_all({"rule": {"kind": "parameter_declaration"}}):
            type_node = param.field("type")
            if type_node is None:
                continue
            type_str = type_node.text().lstrip("*").strip()
            name_node = param.field("name")
            name = name_node.text() if name_node else ""
            result.append({"name": name, "type": type_str})
        # Also capture variadic params: func f(xs ...T)
        for param in params_node.find_all({"rule": {"kind": "variadic_parameter_declaration"}}):
            type_node = param.field("type")
            name_node = param.field("name")
            if type_node is None:
                continue
            result.append({
                "name": name_node.text() if name_node else "",
                "type": f"...{type_node.text().lstrip('*').strip()}",
            })
        if not result:
            return None
        return _json.dumps(result)

    def _go_callee_name(self, func_node) -> str | None:
        """Extract callee name from a Go call expression's function field.

        Only emits a name when the receiver is identifiable without reproducing
        raw source text from chained call expressions (which produces unparseable
        garbage callee strings and inflates edge counts with unresolvable noise).

        Patterns handled:
          identifier              → bare name
          pkg.Function            → "pkg.Function"   (operand is identifier)
          variable.Method         → "variable.Method" (operand is identifier)
          s.field.Method          → "field.Method"   (operand is selector_expression)
          getObj().Method         → None (skip — receiver is a call result)
          a.b().c().d             → None (skip — chained temporary)
        """
        kind = func_node.kind()
        if kind == "identifier":
            return func_node.text()
        if kind == "selector_expression":
            operand = func_node.field("operand")
            field = func_node.field("field")
            if not operand or not field:
                return None
            op_kind = operand.kind()
            if op_kind == "identifier":
                return f"{operand.text()}.{field.text()}"
            if op_kind == "selector_expression":
                # s.field.Method() — use the inner field as receiver
                inner_field = operand.field("field")
                if inner_field:
                    return f"{inner_field.text()}.{field.text()}"
            # call_expression or other complex receiver — skip to avoid garbage names
            return None
        return None

    def _go_fn_ranges(self) -> list[tuple]:
        ranges = []
        root = self._root.root()
        package = self._go_package_name()

        for node in root.find_all({"rule": {"kind": "function_declaration"}}):
            name_node = node.field("name")
            if name_node:
                r = node.range()
                ranges.append((r.start.line, r.end.line, f"{package}.{name_node.text()}"))

        for node in root.find_all({"rule": {"kind": "method_declaration"}}):
            name_node = node.field("name")
            receiver = node.field("receiver")
            if name_node:
                receiver_type = self._go_receiver_type(receiver) if receiver else package
                r = node.range()
                ranges.append((r.start.line, r.end.line, f"{receiver_type}.{name_node.text()}"))

        ranges.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        return ranges

    # ------------------------------------------------------------------
    # Rust: symbols (Phase 3 — stub)
    # ------------------------------------------------------------------

    def _rust_symbols(self) -> list[dict]:
        results = []
        root = self._root.root()
        module = self._basename

        impl_ranges: list[tuple[int, int]] = []
        for impl_node in root.find_all({"rule": {"kind": "impl_item"}}):
            r = impl_node.range()
            impl_ranges.append((r.start.line, r.end.line))

        def _in_impl(start_line: int) -> bool:
            return any(s <= start_line <= e for s, e in impl_ranges)

        # Free functions (not nested inside impl blocks)
        for node in root.find_all({"rule": {"kind": "function_item"}}):
            name_node = node.field("name")
            if name_node is None:
                continue
            r = node.range()
            if _in_impl(r.start.line):
                continue
            fqdn = f"{module}::{name_node.text()}"
            results.append(self._make_symbol(fqdn, node,
                param_types_json=self._rust_param_types(node),
                docstring=self._preceding_comment(node)))

        # impl block methods
        for impl_node in root.find_all({"rule": {"kind": "impl_item"}}):
            type_node = impl_node.field("type")
            type_name = type_node.text() if type_node else module
            body = impl_node.field("body")
            if body is None:
                continue
            for fn_node in body.find_all({"rule": {"kind": "function_item"}}):
                name_node = fn_node.field("name")
                if name_node is None:
                    continue
                fqdn = f"{type_name}::{name_node.text()}"
                results.append(self._make_symbol(fqdn, fn_node,
                    param_types_json=self._rust_param_types(fn_node),
                    docstring=self._preceding_comment(fn_node)))

        return results

    def _rust_param_types(self, fn_node) -> str | None:
        """Extract parameter types from a Rust function_item node.
        Returns JSON list of {"name": str, "type": str} or None if no typed params."""
        params_node = fn_node.field("parameters")
        if params_node is None:
            return None
        result = []
        for param in params_node.find_all({"rule": {"kind": "parameter"}}):
            pattern = param.field("pattern")
            type_node = param.field("type")
            if type_node is None:
                continue
            name = pattern.text() if pattern else ""
            type_str = type_node.text().strip()
            result.append({"name": name, "type": type_str})
        if not result:
            return None
        import json as _json
        return _json.dumps(result)

    def _rust_fn_ranges(self) -> list[tuple]:
        ranges = []
        root = self._root.root()
        module = self._basename

        # Collect line ranges covered by impl blocks so we can exclude nested fn items
        impl_ranges: list[tuple[int, int]] = []
        for impl_node in root.find_all({"rule": {"kind": "impl_item"}}):
            r = impl_node.range()
            impl_ranges.append((r.start.line, r.end.line))

        def _in_impl(start_line: int) -> bool:
            return any(s <= start_line <= e for s, e in impl_ranges)

        # Top-level free functions only (not inside impl blocks)
        for node in root.find_all({"rule": {"kind": "function_item"}}):
            name_node = node.field("name")
            if name_node is None:
                continue
            r = node.range()
            if _in_impl(r.start.line):
                continue
            ranges.append((r.start.line, r.end.line, f"{module}::{name_node.text()}"))

        # impl block methods
        for impl_node in root.find_all({"rule": {"kind": "impl_item"}}):
            type_node = impl_node.field("type")
            type_name = type_node.text() if type_node else module
            body = impl_node.field("body")
            if body is None:
                continue
            for fn_node in body.find_all({"rule": {"kind": "function_item"}}):
                name_node = fn_node.field("name")
                if name_node:
                    r = fn_node.range()
                    ranges.append((r.start.line, r.end.line, f"{type_name}::{name_node.text()}"))

        ranges.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        return ranges

    def _rust_callee_name(self, func_node) -> str | None:
        """Extract callee name from a Rust call expression function field.

        Only emits a name when the receiver is identifiable. Iterator and builder
        method chains produce call_expression receivers whose .text() spans the
        entire chain — emitting that as a callee name produces unresolvable garbage.

        Patterns handled:
          identifier              → bare name
          scoped_identifier       → "Module::Function"
          self.method             → "self.method"
          variable.method         → "variable.method"   (value is identifier)
          self.field.method       → "field.method"       (value is field_expression)
          iter().filter_map(...)  → None (skip — value is call_expression)
          a.b().c().d             → None (skip — chained temporary)
        """
        kind = func_node.kind()
        if kind == "identifier":
            return func_node.text()
        if kind == "scoped_identifier":
            return func_node.text()  # e.g. "Module::Function"
        if kind == "field_expression":
            value = func_node.field("value")
            field = func_node.field("field")
            if not value or not field:
                return None
            method = field.text()
            val_kind = value.kind()
            if val_kind == "self":
                # self.method() — receiver type unknown; filter on the method name,
                # not on "self" which would drop every call through the current struct.
                if method in _RUST_BUILTINS:
                    return None
                return method
            if val_kind == "identifier":
                vt = value.text()
                if vt.isdigit():  # tuple field: self.0.method() → skip
                    return None
                return f"{vt}.{method}"
            if val_kind == "field_expression":
                # self.inner.method() — use inner field as receiver
                inner_field = value.field("field")
                if inner_field:
                    ft = inner_field.text()
                    if ft.isdigit():  # tuple index: self.0.method() → skip
                        return None
                    return f"{ft}.{method}"
            # call_expression or deeper chain — skip to avoid garbage names
            return None
        return None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def detect_language(file_path: str) -> str | None:
    """Infer ast-grep language string from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".h": "c",
        ".cu": "cuda",
        ".cuh": "cuda",
    }.get(ext)
