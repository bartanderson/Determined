# tools/analysis/ingestion/parse_ast.py
# CLAUDE-EDIT 2026-06-16: replaced stub _extract_behavioral_contracts (always
# empty side_effects/raises/testable_behaviors, complexity=0) with full impl
# (docstring pattern matching + AST signals + cyclomatic complexity). Added
# _calculate_complexity(). Wired into parse_ast() in place of `[]`.

from __future__ import annotations

import ast
import builtins
from pathlib import Path
from typing import List, Optional
from determined.ingestion.extract_symbols import extract_symbols
from determined.identity.symbol_identity import SymbolIdentity
from determined.graph.semantic_candidate_builder import SemanticIdentityBuilder

from determined.shared.types import (
    FileAnalysis,
    FileMetadata,
    FunctionRepresentation,
    ClassRepresentation,
    ImportRepresentation,
    SymbolReference,
    BehavioralContract,
    MutationEvent,
)
from determined.graph.symbol_resolution import resolve_symbol_identity
from determined.representation.symbol_environment import (
    SymbolEnvironment,
)
from determined.graph.symbol_router import route_symbol 
from determined.graph.symbol_resolution_engine import resolve_symbol_type

# ----------------------------
# Helpers (pure AST extraction)
# ----------------------------

def _safe_read_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _extract_imports(
    tree: ast.AST,
) -> tuple[List[ImportRepresentation], dict[str, str]]:
    imports: List[ImportRepresentation] = []
    alias_map: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name

                imports.append(
                    ImportRepresentation(
                        module=module_name,
                        import_type="import",
                        line_number=getattr(node, "lineno", -1),
                    )
                )

                local_name = alias.asname or alias.name
                alias_map[local_name] = module_name

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""

            imports.append(
                ImportRepresentation(
                    module=module,
                    import_type="from_import",
                    line_number=getattr(node, "lineno", -1),
                )
            )

            for alias in node.names:
                imported_name = alias.name
                local_name = alias.asname or imported_name

                canonical_name = (
                    f"{module}.{imported_name}"
                    if module
                    else imported_name
                )

                alias_map[local_name] = canonical_name

    return imports, alias_map


def _is_stub(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if the function body contains only stub-like statements."""
    body = node.body
    # skip leading docstring
    start = 1 if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)) else 0
    stmts = body[start:]
    if not stmts:
        return True
    for stmt in stmts:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is ...:
            continue  # bare `...`
        if isinstance(stmt, ast.Raise):
            exc = stmt.exc
            if exc is None:
                continue
            name = getattr(exc, "id", None) or getattr(getattr(exc, "func", None), "id", None)
            if name == "NotImplementedError":
                continue
        if isinstance(stmt, ast.Return) and (stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None)):
            continue
        return False
    return True


def _extract_functions(tree: ast.AST) -> List[FunctionRepresentation]:
    results: List[FunctionRepresentation] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [
                arg.arg
                for arg in node.args.args
                if arg.arg != "self"
            ]

            results.append(
                FunctionRepresentation(
                    name=node.name,
                    line_number=node.lineno,
                    arguments=args,
                    return_type=ast.unparse(node.returns) if getattr(node, "returns", None) else None,
                    docstring=ast.get_docstring(node),
                    is_stub=_is_stub(node),
                )
            )

    return results


def _extract_classes(tree: ast.AST) -> List[ClassRepresentation]:
    results: List[ClassRepresentation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]

            results.append(
                ClassRepresentation(
                    name=node.name,
                    line_number=node.lineno,
                    methods=methods,
                    base_classes=[ast.unparse(b) for b in node.bases],
                    docstring=ast.get_docstring(node),
                )
            )

    return results

def _extract_symbol_references(
    tree: ast.AST,
    known_symbols: set[str],
    alias_map: dict[str, str],
    module_name: str,
    project_symbols: set[str] | None = None,
) -> list[SymbolReference]:

    results = []
    local_symbol_map = {}

    runtime_bindings = _extract_runtime_bindings(
        tree,
        alias_map={
            "ctx": "determined.context",
        }
    )

    identity_builder = SemanticIdentityBuilder()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local_symbol_map[node.name] = node.name

    def safe_resolve(module_name: str, raw: str) -> str:
        # detect poisoned module names (filesystem paths)
        if ":" in module_name or "\\" in module_name or module_name.startswith("C:"):
            return raw  # DO NOT propagate filesystem namespace

        return f"{module_name}.{raw}"

    class Visitor(ast.NodeVisitor):

        def __init__(self):
            self.current_function = "<module>"

        def visit_FunctionDef(self, node):
            prev = self.current_function
            self.current_function = node.name

            self.generic_visit(node)

            self.current_function = prev

        def visit_Call(self, node):

            raw = None
            resolved = None

            # ----------------------
            # CASE 1: direct call
            # ----------------------
            if isinstance(node.func, ast.Name):

                raw = node.func.id

                resolved = (
                    alias_map.get(raw)
                    or runtime_bindings.get(raw)
                    or local_symbol_map.get(raw)
                )

                if resolved is None:

                    # builtin calls should remain canonical
                    if raw in dir(builtins):
                        resolved = raw
                    else:
                        resolved = safe_resolve(module_name, raw)

            # ----------------------
            # CASE 2: attribute call
            # ----------------------
            elif isinstance(node.func, ast.Attribute):

                base = node.func.value

                # import_alias.func()
                if isinstance(base, ast.Name):

                    base_name = alias_map.get(base.id)

                    if base_name is not None:
                        raw = f"{base_name}.{node.func.attr}"
                        resolved = raw
                    else:
                        # obj.method() where obj is a local/param/self - we can't
                        # resolve obj's type without inference, but record the call
                        # keyed on receiver.method so in_degree counts it
                        # (matched downstream by callee LIKE '%.method'). Without
                        # this, every method only ever called as instance.method()
                        # looks like dead code.
                        raw = f"{base.id}.{node.func.attr}"
                        resolved = raw

                # chained.attr.call()
                elif isinstance(base, ast.Attribute):

                    parts = []

                    current = base

                    while isinstance(current, ast.Attribute):
                        parts.append(current.attr)
                        current = current.value

                    if isinstance(current, ast.Name):

                        parts.append(
                            alias_map.get(current.id, current.id)
                        )

                        raw = ".".join(
                            list(reversed(parts)) + [node.func.attr]
                        )

                        resolved = raw

                    else:
                        self.generic_visit(node)
                        return

                else:
                    self.generic_visit(node)
                    return

            # ----------------------
            # unresolved
            # ----------------------
            if raw is None:
                self.generic_visit(node)
                return

            env = SymbolEnvironment(
                alias_map=alias_map,
                runtime_bindings=runtime_bindings,
                project_symbols=known_symbols,
            )

            route_type = resolve_symbol_type(
                name=raw,
                runtime_bindings=env.runtime_bindings or {},
                project_symbols=env.project_symbols or set(),
                project_prefixes=None,
            )

            if route_type is None:
                route_type = "unknown"

            identity = identity_builder.build(
                name=raw,
                env=env,
                route_type=route_type,
            )

            fqdn = identity.fqdn or resolved or raw

            identity = SymbolIdentity(
                surface=raw,
                normalized = raw,
                fqdn=fqdn,
                module=fqdn,
                kind=(
                    "runtime"
                    if raw in runtime_bindings
                    else "unknown"
                ),
                provenance=[
                    "cp0_raw",
                    "cp1_normalized",
                    "cp2_resolve",
                ],
                confidence=identity.confidence,
            )

            results.append((
                self.current_function,
                identity,
                node.lineno,
            ))

            self.generic_visit(node)

    Visitor().visit(tree)

    return [
        SymbolReference(
            caller=caller,
            callee=identity.fqdn or identity.surface,
            line_number=lineno,
            identity=identity,
        )
        for (caller, identity, lineno) in results
    ]


def _extract_mutations(tree: ast.AST) -> List[MutationEvent]:
    # Build a map of (start_line, end_line) -> first docstring line for each
    # function, so each mutation can be annotated with the intent of the
    # function it lives in.
    func_intents: List[tuple] = []  # (start, end, intent_str)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node) or ""
            intent = doc.split("\n")[0].strip() if doc else ""
            end = getattr(node, "end_lineno", node.lineno)
            func_intents.append((node.lineno, end, intent))

    def _intent_for_line(lineno: int) -> str:
        for start, end, intent in func_intents:
            if start <= lineno <= end:
                return intent
        return ""

    mutations: List[MutationEvent] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            target = None
            if isinstance(node.func.value, ast.Name):
                target = node.func.value.id

            if target:
                mutations.append(
                    MutationEvent(
                        line_number=node.lineno,
                        target=target,
                        operation=node.func.attr,
                        raw_expression=ast.unparse(node),
                        intent=_intent_for_line(node.lineno),
                    )
                )

    return mutations


def _calculate_complexity(node: ast.FunctionDef) -> int:
    """Cyclomatic complexity: 1 + branches."""
    complexity = 1
    for subnode in ast.walk(node):
        if isinstance(subnode, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(subnode, ast.BoolOp):
            complexity += len(subnode.values) - 1
    return complexity


def _extract_behavioral_contracts(tree: ast.AST) -> List[BehavioralContract]:
    """
    Extract behavioral contracts from function docstrings and AST structure.

    Produces:
      - description from first docstring line
      - side_effects inferred from docstring patterns
      - raises extracted from Raises: section
      - testable_behaviors tagged from docstring + AST signals
      - complexity_score (cyclomatic)

    Only emits a contract when there is something meaningful to say
    (description, side effects, testable behaviors, or complexity > 3).
    """
    import re

    SIDE_EFFECT_PATTERNS = [
        (r'(?:updates?|modifies?|changes?|sets?)\s+(?:the\s+)?(\w+)', 'mutates {}'),
        (r'(?:saves?|persists?|stores?)\s+(?:to|into)?\s+(\w+)',      'saves to {}'),
        (r'(?:creates?|initializes?|builds?)\s+(?:a\s+)?(?:new\s+)?(\w+)', 'creates {}'),
        (r'(?:sends?|emits?|triggers?)\s+(?:a\s+)?(\w+)',             'sends {}'),
        (r'(?:clears?|resets?|removes?)\s+(?:the\s+)?(\w+)',          'clears {}'),
    ]

    AI_CALLS     = {'generate_text', 'generate_structured_data', 'generate_embedding'}
    DB_CALLS     = {'execute', 'commit', 'fetchone', 'fetchall'}

    contracts: List[BehavioralContract] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        doc = ast.get_docstring(node) or ""
        complexity = _calculate_complexity(node)

        description = doc.split("\n")[0].strip()[:150] if doc else ""
        side_effects: List[str] = []
        raises: List[str] = []
        testable_behaviors: List[str] = []

        # --- docstring signals ---
        if doc:
            doc_lower = doc.lower()

            for pattern, template in SIDE_EFFECT_PATTERNS:
                for match in re.finditer(pattern, doc_lower):
                    effect = template.format(match.group(1))
                    if effect not in side_effects:
                        side_effects.append(effect)

            if 'raises:' in doc_lower or 'raises ' in doc_lower:
                raise_section = re.search(
                    r'raises:?\s*(.+?)(?:\n\n|\Z)', doc_lower, re.DOTALL
                )
                if raise_section:
                    exceptions = re.findall(
                        r'\b([A-Z][a-zA-Z]*(?:Error|Exception))\b',
                        raise_section.group(1)
                    )
                    raises = list(set(exceptions))

            if 'example' in doc_lower or '>>>' in doc:
                testable_behaviors.append('has_doctest_examples')
            if 'returns' in doc_lower:
                testable_behaviors.append('verifiable_return_value')
            if raises:
                testable_behaviors.append('exception_conditions')
            if side_effects:
                testable_behaviors.append('state_change_verification')

        # --- AST signals ---
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call) and isinstance(subnode.func, ast.Attribute):
                attr = subnode.func.attr
                if attr in AI_CALLS and 'ai_dependency_mock_required' not in testable_behaviors:
                    testable_behaviors.append('ai_dependency_mock_required')
                if attr in DB_CALLS and 'database_interaction' not in testable_behaviors:
                    testable_behaviors.append('database_interaction')

            if isinstance(subnode, ast.Assign):
                targets = subnode.targets
                if (
                    targets
                    and isinstance(targets[0], ast.Attribute)
                    and isinstance(targets[0].value, ast.Name)
                    and targets[0].value.id in ('self', 'cls')
                    and 'internal_state_change' not in testable_behaviors
                ):
                    testable_behaviors.append('internal_state_change')

        # only emit when there is something useful to say
        if description or side_effects or testable_behaviors or complexity > 3:
            contracts.append(
                BehavioralContract(
                    function_name=node.name,
                    line_number=node.lineno,
                    description=description,
                    side_effects=side_effects,
                    raises=raises,
                    testable_behaviors=testable_behaviors,
                    complexity_score=complexity,
                )
            )

    return contracts


# ----------------------------
# Core API (the only thing other modules should call)
# ----------------------------

def parse_ast(
    file_path: str | Path,
    global_known_symbols: set[str] | None = None,
    runtime_bindings: dict[str, str] | None = None,
    ) -> Optional[FileAnalysis]:

    runtime_bindings = runtime_bindings or {}

    path = Path(file_path)

    normalized_path = str(path).replace("\\", "/")

    if "tools/" in normalized_path:
        normalized_path = normalized_path.split("tools/", 1)[1]
        module_name = (
            "tools."
            + normalized_path.removesuffix(".py").replace("/", ".")
        )
    else:
        module_name = path.stem

    source = _safe_read_file(path)
    if source is None:
        print("PARSE_AST DROP: source is None for", file_path)
        print("PARSE_AST RETURN NONE:", file_path)
        return None

    try:
        import warnings as _warnings
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore", DeprecationWarning)
            tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        print("PARSE_AST SYNTAX ERROR:", file_path)
        print("  error:", repr(e))
        return None
    except Exception as e:
        print("PARSE_AST UNKNOWN ERROR:", file_path)
        print("  error:", repr(e))
        return None

    functions = _extract_functions(tree)
    classes = _extract_classes(tree)
    imports, alias_map = _extract_imports(tree)
    known_symbols = global_known_symbols or set()
    project_symbols = global_known_symbols or set()

    # TRACKER.md item 23: runtime_bindings was only ever the caller's
    # parameter (always {} from scan_project_files.py's placeholder),
    # even though _extract_symbol_references() below computes the real
    # tree-derived bindings internally via _extract_runtime_bindings() -
    # it just never returned/exposed them. Recomputing here (deliberately
    # redundant with that internal call, rather than changing its return
    # signature and risking its other direct caller,
    # tests/debug/test_symbol_pipeline_trace.py) so FileAnalysis.runtime_bindings
    # (set below) actually reflects real bindings instead of staying
    # permanently empty in production - the "runtime" classification
    # bucket was dead because of this.
    detected_runtime_bindings = _extract_runtime_bindings(
        tree,
        alias_map={"ctx": "determined.context"},
    )
    runtime_bindings = {**detected_runtime_bindings, **runtime_bindings}

    symbol_references = _extract_symbol_references(
        tree,
        known_symbols,
        alias_map,
        module_name,
        project_symbols,
    )
    
    mutations = _extract_mutations(tree)

    return FileAnalysis(
        file_path=str(path).replace("\\", "/"),
        metadata=FileMetadata(
            line_count=len(source.splitlines()),
            is_hot=bool(mutations),
            role=None,
        ),

        functions=functions,
        classes=classes,
        imports=imports,
        mutations=mutations,
        symbol_references=symbol_references,

        runtime_bindings=runtime_bindings,

        behavioral_contracts=_extract_behavioral_contracts(tree),
    )

def _extract_attribute_chains(tree: ast.AST):
    chains = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts = []
            cur = node

            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value

            if isinstance(cur, ast.Name):
                parts.append(cur.id)

            full = ".".join(reversed(parts))
            chains.add(full)

    return chains

def _extract_runtime_bindings(
    tree: ast.AST,
    alias_map: dict[str, str] | None = None,
) -> dict[str, str]:
    alias_map = alias_map or {}

    bindings = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                var_name = node.targets[0].id

                # handle constructor calls
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name):
                        bindings[var_name] = node.value.func.id

                    elif isinstance(node.value.func, ast.Attribute):
                        parts = []
                        cur = node.value.func
                        while isinstance(cur, ast.Attribute):
                            parts.append(cur.attr)
                            cur = cur.value
                        if isinstance(cur, ast.Name):
                            parts.append(cur.id)
                            bindings[var_name] = ".".join(reversed(parts))
                            
                # NEW: direct imported symbol rebinding
                elif isinstance(node.value, ast.Name):

                    imported = alias_map.get(node.value.id)

                    if imported:
                        bindings[var_name] = imported

                # NEW: handle attribute assignments with alias-aware canonicalization
                # (Flask injection, containers, globals, imported module aliases)
                elif isinstance(node.value, ast.Attribute):
                    parts = []
                    cur = node.value

                    while isinstance(cur, ast.Attribute):
                        parts.append(cur.attr)
                        cur = cur.value

                    if isinstance(cur, ast.Name):
                        root = cur.id

                        # STEP 1: resolve alias FIRST (strict)
                        base = alias_map.get(root, root)

                        # STEP 2: if base is already canonical module path,
                        # treat attribute chain as extension of that module
                        if "." in base:
                            resolved = base + "." + ".".join(reversed(parts))
                        else:
                            resolved = ".".join(reversed(parts + [base]))

                        # forward mapping (for completeness)
                        bindings[var_name] = resolved

                        # REVERSE mapping (what router actually needs)
                        bindings[resolved] = var_name

    assert isinstance(bindings, dict), "runtime bindings must be dict"
    return bindings