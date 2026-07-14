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
    "Some", "None", "Ok", "Err", "Self", "self", "super",
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
        self._file_path = file_path
        self._language = language
        self._root = SgRoot(src, language)
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
        return []

    def call_edges(self) -> list[tuple]:
        """
        Return list of (caller_fqdn, callee_name, 'static', resolved: bool).
        resolved is False at this stage; cross-file resolution happens in persist layer.
        """
        lang = self._language
        if lang not in ("javascript", "typescript", "jsx", "tsx", "go", "rust"):
            return []
        return self._shared_call_edges(self._lang_spec())

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
            results.append(self._make_symbol(fqdn, node, is_stub=self._js_is_stub(node)))

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
                results.append(self._make_symbol(fqdn, decl, is_stub=self._js_is_stub(val_node)))

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
                results.append(self._make_symbol(fqdn, method, is_stub=self._js_is_stub(method)))

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

    def _make_symbol(self, fqdn: str, node, is_stub: bool = False) -> dict:
        return {
            "file_path": self._file_path,
            "name": fqdn,
            "line_number": node.range().start.line + 1,
            "return_type": None,
            "arguments_json": "[]",
            "param_types_json": None,
            "docstring": None,
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

    def _js_callee_name(self, func_node) -> str | None:
        """Extract callee name from the function field of a call_expression."""
        kind = func_node.kind()
        if kind == "identifier":
            return func_node.text()
        if kind == "member_expression":
            obj = func_node.field("object")
            prop = func_node.field("property")
            if obj and prop:
                return f"{obj.text()}.{prop.text()}"
        return None

    # ------------------------------------------------------------------
    # JS/TS: data flow edges
    # ------------------------------------------------------------------

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
            results.append(self._make_symbol(fqdn, node))

        # Method declarations: func (r ReceiverType) MethodName(...) ...
        for node in root.find_all({"rule": {"kind": "method_declaration"}}):
            name_node = node.field("name")
            receiver = node.field("receiver")
            if name_node is None:
                continue
            receiver_type = self._go_receiver_type(receiver) if receiver else package
            method_name = name_node.text()
            fqdn = f"{receiver_type}.{method_name}"
            results.append(self._make_symbol(fqdn, node))

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

    def _go_callee_name(self, func_node) -> str | None:
        """Extract callee name from a Go call expression's function field."""
        kind = func_node.kind()
        if kind == "identifier":
            return func_node.text()
        if kind == "selector_expression":
            operand = func_node.field("operand")
            field = func_node.field("field")
            if operand and field:
                return f"{operand.text()}.{field.text()}"
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
            results.append(self._make_symbol(fqdn, node))

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
                results.append(self._make_symbol(fqdn, fn_node))

        return results

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
        """Extract callee name from a Rust call expression function field."""
        kind = func_node.kind()
        if kind == "identifier":
            return func_node.text()
        if kind == "scoped_identifier":
            return func_node.text()  # e.g. "Module::Function"
        if kind == "field_expression":
            # receiver.method — emit "receiver.method" for consistency with Go
            value = func_node.field("value")
            field = func_node.field("field")
            if value and field:
                return f"{value.text()}.{field.text()}"
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
    }.get(ext)
