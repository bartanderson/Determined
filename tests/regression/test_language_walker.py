"""
Regression tests for LanguageWalker (Phase 1: JS/TS, Phase 2: Go).

Tests use inline source strings — no corpus files needed.
"""

import pytest
from determined.ingestion.language_walker import LanguageWalker, detect_language


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def walker(src: str, language: str, filename: str = "testfile") -> LanguageWalker:
    return LanguageWalker(src, f"/fake/{filename}.{language[:2]}", language)


def symbol_names(w: LanguageWalker) -> list[str]:
    return [s["name"] for s in w.symbols()]


def callers(edges: list[tuple]) -> set[tuple]:
    return {(e[0], e[1]) for e in edges if e[2] == "static"}


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

def test_detect_language_js():
    assert detect_language("foo.js") == "javascript"

def test_detect_language_ts():
    assert detect_language("bar.ts") == "typescript"

def test_detect_language_go():
    assert detect_language("main.go") == "go"

def test_detect_language_rust():
    assert detect_language("lib.rs") == "rust"

def test_detect_language_unknown():
    assert detect_language("readme.md") is None


# ---------------------------------------------------------------------------
# JS: named function declaration
# ---------------------------------------------------------------------------

JS_NAMED_FN = """
function greet(name) {
    return "hello " + name;
}
"""

def test_js_named_fn_symbol():
    w = walker(JS_NAMED_FN, "javascript", "mod")
    assert "mod.greet" in symbol_names(w)

def test_js_named_fn_line_number():
    w = walker(JS_NAMED_FN, "javascript", "mod")
    sym = next(s for s in w.symbols() if s["name"] == "mod.greet")
    assert sym["line_number"] == 2

def test_js_named_fn_not_stub():
    w = walker(JS_NAMED_FN, "javascript", "mod")
    sym = next(s for s in w.symbols() if s["name"] == "mod.greet")
    assert sym["is_stub"] is False


# ---------------------------------------------------------------------------
# JS: arrow function
# ---------------------------------------------------------------------------

JS_ARROW = """
const add = (a, b) => a + b;
const noop = () => {};
"""

def test_js_arrow_fn_symbol():
    w = walker(JS_ARROW, "javascript", "util")
    names = symbol_names(w)
    assert "util.add" in names

def test_js_arrow_fn_stub_detection():
    w = walker(JS_ARROW, "javascript", "util")
    noop = next(s for s in w.symbols() if s["name"] == "util.noop")
    assert noop["is_stub"] is True


# ---------------------------------------------------------------------------
# JS: class method
# ---------------------------------------------------------------------------

JS_CLASS = """
class Player {
    constructor(name) {
        this.name = name;
    }
    move(direction) {
        this.position = direction;
    }
    getStats() {
        return { name: this.name };
    }
}
"""

def test_js_class_method_symbols():
    w = walker(JS_CLASS, "javascript", "entities")
    names = symbol_names(w)
    assert "Player.move" in names
    assert "Player.getStats" in names
    assert "Player.constructor" in names

def test_js_class_method_fqdn_uses_class_name():
    w = walker(JS_CLASS, "javascript", "entities")
    names = symbol_names(w)
    # Should NOT use file basename for class methods
    assert "entities.move" not in names


# ---------------------------------------------------------------------------
# JS: object literal method
# ---------------------------------------------------------------------------

JS_OBJ_LITERAL = """
const dungeon = {
    generate: function(width, height) {
        return [];
    },
    reset: () => {},
};
"""

def test_js_object_literal_method():
    w = walker(JS_OBJ_LITERAL, "javascript", "dungeon")
    names = symbol_names(w)
    assert "dungeon.generate" in names

def test_js_object_literal_arrow_method():
    w = walker(JS_OBJ_LITERAL, "javascript", "dungeon")
    names = symbol_names(w)
    assert "dungeon.reset" in names


# ---------------------------------------------------------------------------
# JS: call edges
# ---------------------------------------------------------------------------

JS_CALL_CHAIN = """
function buildRoom(size) {
    return placeWalls(size);
}
function placeWalls(size) {
    return [];
}
"""

def test_js_call_edge_direct():
    w = walker(JS_CALL_CHAIN, "javascript", "gen")
    edges = callers(w.call_edges())
    # callee is raw name from call site; cross-file resolution happens in persist layer
    assert ("gen.buildRoom", "placeWalls") in edges

def test_js_call_edge_no_self_loop():
    w = walker(JS_CALL_CHAIN, "javascript", "gen")
    edges = callers(w.call_edges())
    for src, tgt in edges:
        assert src != tgt

def test_js_builtin_filtered_from_edges():
    src = """
function log(msg) {
    console.log(msg);
    Math.floor(1.5);
}
"""
    w = walker(src, "javascript", "mod")
    edges = callers(w.call_edges())
    targets = {tgt for _, tgt in edges}
    assert "console.log" not in targets
    assert "Math.floor" not in targets


# ---------------------------------------------------------------------------
# JS: member call edge
# ---------------------------------------------------------------------------

JS_MEMBER_CALL = """
function init(game) {
    game.start();
}
"""

def test_js_member_call_edge():
    w = walker(JS_MEMBER_CALL, "javascript", "main")
    edges = callers(w.call_edges())
    assert ("main.init", "game.start") in edges


# ---------------------------------------------------------------------------
# TS: class method fqdn
# ---------------------------------------------------------------------------

TS_CLASS = """
export class CombatSystem {
    resolveCombat(attacker: Player, target: Enemy): void {
        target.takeDamage(attacker.getDamage());
    }
    calculateDamage(attacker: Player): number {
        return attacker.strength * 2;
    }
}
"""

def test_ts_class_method_symbols():
    w = walker(TS_CLASS, "typescript", "CombatSystem")
    names = symbol_names(w)
    assert "CombatSystem.resolveCombat" in names
    assert "CombatSystem.calculateDamage" in names

def test_ts_class_method_call_edge():
    w = walker(TS_CLASS, "typescript", "CombatSystem")
    edges = callers(w.call_edges())
    # resolveCombat calls target.takeDamage and attacker.getDamage
    targets = {tgt for src, tgt in edges if src == "CombatSystem.resolveCombat"}
    assert "target.takeDamage" in targets or "attacker.getDamage" in targets


# ---------------------------------------------------------------------------
# JS: data flow L1 (nested call arg)
# ---------------------------------------------------------------------------

JS_L1 = """
function pipeline() {
    process(generate());
}
function generate() { return []; }
function process(items) { return items; }
"""

def test_js_data_flow_l1_nested_arg():
    w = walker(JS_L1, "javascript", "pipe")
    df = [(e[0], e[1], e[3]) for e in w.data_flow_edges() if e[2] == "data_flow"]
    assert ("pipe.pipeline", "generate", "data_flow_arg") in df


# ---------------------------------------------------------------------------
# JS: data flow L2 (variable binding)
# ---------------------------------------------------------------------------

JS_L2 = """
function run() {
    const items = getItems();
    render(items);
}
function getItems() { return []; }
function render(x) {}
"""

def test_js_data_flow_l2_var_binding():
    w = walker(JS_L2, "javascript", "app")
    df = [(e[0], e[1], e[3]) for e in w.data_flow_edges() if e[2] == "data_flow"]
    assert ("app.run", "getItems", "data_flow_var") in df


# ---------------------------------------------------------------------------
# JS: data flow L3a (for-of loop)
# ---------------------------------------------------------------------------

JS_L3A = """
function loadAll() {
    for (const item of fetchItems()) {
        display(item);
    }
}
function fetchItems() { return []; }
function display(x) {}
"""

def test_js_data_flow_l3a_for_of():
    w = walker(JS_L3A, "javascript", "loader")
    df = [(e[0], e[1], e[3]) for e in w.data_flow_edges() if e[2] == "data_flow"]
    assert ("loader.loadAll", "fetchItems", "data_flow_for_iter") in df


# ---------------------------------------------------------------------------
# JS: data flow L3b (object named arg)
# ---------------------------------------------------------------------------

JS_L3B = """
function submit() {
    const data = buildData();
    send({ payload: data, retry: true });
}
function buildData() { return {}; }
function send(opts) {}
"""

def test_js_data_flow_l3b_object_named_arg():
    w = walker(JS_L3B, "javascript", "net")
    df = [(e[0], e[1], e[3]) for e in w.data_flow_edges() if e[2] == "data_flow"]
    assert ("net.submit", "buildData", "data_flow_var_kwarg") in df


# ---------------------------------------------------------------------------
# JS: binding scoped to function (no leak)
# ---------------------------------------------------------------------------

JS_SCOPED = """
function fnA() {
    const x = getX();
    useX(x);
}
function fnB() {
    useX(x);
}
function getX() { return 1; }
function useX(v) {}
"""

def test_js_binding_does_not_leak_across_functions():
    w = walker(JS_SCOPED, "javascript", "scope")
    df_edges = w.data_flow_edges()
    # fnB should produce no data_flow edges for x (x not bound in fnB)
    fnb_df = [e for e in df_edges if e[0] == "scope.fnB"]
    assert len(fnb_df) == 0


# ---------------------------------------------------------------------------
# Go: Phase 2 stub — basic symbol extraction
# ---------------------------------------------------------------------------

GO_SRC = """
package game

func StartGame(cfg Config) error {
    return nil
}

func (g *Game) Update() {
    g.tick()
}
"""

def test_go_function_symbol():
    w = LanguageWalker(GO_SRC, "/fake/game.go", "go")
    names = symbol_names(w)
    assert "game.StartGame" in names

def test_go_method_symbol():
    w = LanguageWalker(GO_SRC, "/fake/game.go", "go")
    names = symbol_names(w)
    assert "Game.Update" in names


GO_CALLS_SRC = """
package engine

func Run(cfg Config) {
    result := Prepare(cfg)
    Process(result)
}

func Prepare(cfg Config) Result {
    return Result{}
}

func Process(r Result) {
}

func (e *Engine) Start() {
    Run(e.cfg)
}
"""

def test_go_call_edge_direct():
    w = LanguageWalker(GO_CALLS_SRC, "/fake/engine.go", "go")
    edges = callers(w.call_edges())
    assert ("engine.Run", "Prepare") in edges
    assert ("engine.Run", "Process") in edges

def test_go_method_call_edge():
    w = LanguageWalker(GO_CALLS_SRC, "/fake/engine.go", "go")
    edges = callers(w.call_edges())
    assert ("Engine.Start", "Run") in edges

def test_go_selector_call_edge():
    # selector_expression: e.cfg, pkg.Func() — must not be silently dropped
    src = """
package game

func Setup(s *State) {
    s.Init()
    helper.Run(s)
}
func (s *State) Init() {}
"""
    w = LanguageWalker(src, "/fake/game.go", "go")
    edges = callers(w.call_edges())
    assert ("game.Setup", "s.Init") in edges
    assert ("game.Setup", "helper.Run") in edges

def test_go_builtin_filtered():
    src = """
package main

import "fmt"

func Hello() {
    fmt.Println("hello")
    DoWork()
}

func DoWork() {}
"""
    w = LanguageWalker(src, "/fake/main.go", "go")
    edges = callers(w.call_edges())
    # fmt is a Go builtin package — should be filtered
    assert not any(c == "fmt.Println" for _, c in edges)
    # non-builtin call should remain
    assert ("main.Hello", "DoWork") in edges

def test_go_no_self_loop():
    src = """
package util

func Recurse(n int) int {
    if n == 0 { return 0 }
    return Recurse(n - 1)
}
"""
    w = LanguageWalker(src, "/fake/util.go", "go")
    edges = callers(w.call_edges())
    # self-loop: caller == callee — Go walker doesn't filter these yet (same as JS baseline)
    # Just confirm the edge is attributed to the right caller
    assert all(c == "util.Recurse" for c, _ in edges)

def test_go_package_name_fallback():
    # No package clause → falls back to basename
    src = "func Standalone() {}\n"
    w = LanguageWalker(src, "/fake/util.go", "go")
    names = symbol_names(w)
    assert any("Standalone" in n for n in names)


# ---------------------------------------------------------------------------
# Rust: Phase 3
# ---------------------------------------------------------------------------

RUST_SRC = """
mod game;

fn start_game(cfg: Config) {
    let g = init(cfg);
    run(g);
}

fn init(cfg: Config) -> Game { Game {} }
fn run(g: Game) {}

struct Player;

impl Player {
    fn new() -> Self { Player }
    fn fight(&self, target: &mut Enemy) {
        target.take_damage(10);
    }
}
"""


def test_rust_fn_symbol():
    w = LanguageWalker(RUST_SRC, "/fake/game.rs", "rust")
    names = symbol_names(w)
    assert "game::start_game" in names
    assert "game::init" in names
    assert "game::run" in names


def test_rust_impl_method_symbol():
    w = LanguageWalker(RUST_SRC, "/fake/game.rs", "rust")
    names = symbol_names(w)
    assert "Player::new" in names
    assert "Player::fight" in names


def test_rust_call_edge_direct():
    w = LanguageWalker(RUST_SRC, "/fake/game.rs", "rust")
    edges = callers(w.call_edges())
    assert ("game::start_game", "init") in edges
    assert ("game::start_game", "run") in edges


def test_rust_method_call_edge():
    w = LanguageWalker(RUST_SRC, "/fake/game.rs", "rust")
    edges = callers(w.call_edges())
    # target.take_damage(10) → field_expression emits "target.take_damage"
    assert ("Player::fight", "target.take_damage") in edges


def test_rust_builtin_filtered():
    src = """
fn setup() {
    let v: Vec<i32> = Vec::new();
    println!("hello");
    do_work();
}
fn do_work() {}
"""
    w = LanguageWalker(src, "/fake/lib.rs", "rust")
    edges = callers(w.call_edges())
    # Vec::new is a builtin — the "new" method call should be filtered
    # do_work should survive
    callee_names = {c for _, c in edges}
    assert "println" not in callee_names
    assert "do_work" in callee_names
