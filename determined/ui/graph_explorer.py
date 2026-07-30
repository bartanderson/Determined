"""
graph_explorer.py — interactive call-graph explorer using raylib.

Launch from the UI via the Map tab "Open Explorer" button (subprocess),
or directly: python tools/graph_explorer.py <db_path_or_corpus_name>

Controls
--------
  Scroll wheel       Zoom (centered on cursor)
  Left drag          Pan
  Middle drag        Pan (alternate)
  Left click node    Select — loads inspection panel
  Double-click node  Expand — show immediate neighbors, fade rest
  Escape             Collapse expand / clear selection
  F                  Frame selected node (or all if none)
  /                  Focus search bar
  Ctrl+0             Reset zoom/pan
"""

from __future__ import annotations

import math
import random
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import subprocess

import raylib as rl
from raylib import ffi

try:
    import socketio as _sio_mod
    _SOCKETIO_AVAILABLE = True
except ImportError:
    _SOCKETIO_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCREEN_W, SCREEN_H = 1400, 900
PANEL_W = 300          # right inspection panel width
GRAPH_W = SCREEN_W - PANEL_W
MINIMAP_W, MINIMAP_H = 220, 150
MINIMAP_MARGIN = 12

MAX_INITIAL_NODES = 120   # shown on first load
NODE_RADIUS_BASE = 7.0
NODE_RADIUS_MAX  = 22.0
NODE_MIN_SCREEN_PX = 3    # minimum visible size at any zoom
EDGE_ALPHA_NORMAL   = 80   # 0-255
EDGE_ALPHA_SELECTED = 200
FPS = 60
ZOOM_MIN = 0.08
ZOOM_MAX = 10.0

# Text scale steps — cycle with + / - keys
TEXT_SCALE_STEPS = [0.75, 1.0, 1.25, 1.5, 2.0]
TEXT_SCALE_DEFAULT = 1  # index into TEXT_SCALE_STEPS

_CTX_MENU_ITEMS = [
    ("Open in Workbench", "workbench"),
    ("Ask Oracle",        "oracle"),
    ("Show in Map",       "map"),
    ("Call Tree",         "call_tree"),
    ("Open in Editor",    "editor"),
    None,  # divider
    ("Expand node",       "expand"),
    ("Frame node",        "frame"),
    None,  # divider
    ("Copy name",         "copy_name"),
    ("Copy file path",    "copy_path"),
]
_CTX_MENU_W   = 178
_CTX_MENU_H   = 22   # per item
_CTX_MENU_DIV = 8    # divider height

# Font path — Segoe UI on Windows, fallback to None (raylib default)
import os as _os
_FONT_PATH = r"C:\Windows\Fonts\segoeui.ttf"
_FONT_AVAILABLE = _os.path.exists(_FONT_PATH)

# Colours  (r, g, b, a)
COL_BG          = (18,  20,  26,  255)
COL_PANEL_BG    = (24,  26,  34,  255)
COL_PANEL_BORDER= (50,  55,  70,  255)
COL_NODE_NORMAL = (80, 120, 200,  255)
COL_NODE_STUB   = (220, 130,  40,  255)
COL_NODE_TOOL   = ( 60, 200, 160,  255)
COL_NODE_SEL    = (255, 255, 255,  255)
COL_NODE_CALLER = ( 80, 220, 100,  255)   # neighbors that call selected
COL_NODE_CALLEE = (220,  80, 100,  255)   # neighbors selected calls
COL_NODE_FADED  = ( 40,  45,  60,  255)
COL_EDGE_NORMAL = ( 80,  90, 120,  EDGE_ALPHA_NORMAL)
COL_EDGE_SEL    = (180, 200, 255,  EDGE_ALPHA_SELECTED)
COL_TEXT        = (200, 205, 215,  255)
COL_TEXT_DIM    = (100, 108, 125,  255)
COL_SEARCH_BG   = ( 30,  33,  44,  255)
COL_SEARCH_BDR  = ( 70,  80, 110,  255)
COL_MINIMAP_BG  = ( 20,  22,  30, 200)
COL_MINIMAP_VP  = (100, 140, 220, 120)

def _col(r, g, b, a=255):
    c = ffi.new('Color *')
    c.r, c.g, c.b, c.a = r, g, b, a
    return c[0]

def _v2(x, y):
    v = ffi.new('Vector2 *')
    v.x, v.y = float(x), float(y)
    return v[0]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Node:
    id: int
    name: str
    file_path: str
    is_stub: bool
    is_tool: bool
    degree: int = 0        # total edge count
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0

    @property
    def radius(self) -> float:
        return min(NODE_RADIUS_BASE + math.sqrt(self.degree) * 1.2, NODE_RADIUS_MAX)

    @property
    def short_name(self) -> str:
        return self.name.split("::")[-1] if "::" in self.name else self.name

    @property
    def color(self):
        if self.is_tool:   return COL_NODE_TOOL
        if self.is_stub:   return COL_NODE_STUB
        return COL_NODE_NORMAL


@dataclass
class Edge:
    src_id: int
    dst_id: int


# ---------------------------------------------------------------------------
# DB loader
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Socket bridge — connects graph explorer to the Determined UI server
# ---------------------------------------------------------------------------

class _SocketBridge:
    """Non-blocking socket.io client that links the graph explorer to the UI.

    If the UI is not running the bridge silently does nothing.
    All public methods are safe to call from any thread.
    """

    UI_URL = "http://localhost:5050"

    def __init__(self):
        self._sio = None
        self._connected = False
        self._pending_highlight: Optional[str] = None
        if _SOCKETIO_AVAILABLE:
            threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        # Retry indefinitely — UI may start after graph explorer.
        while True:
            try:
                sio = _sio_mod.Client(reconnection=True, reconnection_attempts=0,
                                      logger=False, engineio_logger=False)

                @sio.on("gx_highlight")
                def on_highlight(data):
                    self._pending_highlight = data.get("symbol")

                sio.connect(self.UI_URL, transports=["websocket"])
                self._sio = sio
                self._connected = True
                return  # connected — done
            except Exception:
                self._connected = False
                time.sleep(5)  # UI not running yet — retry in 5s

    def emit_select(self, node):
        if not self._connected:
            return
        try:
            self._sio.emit("gx_select", {
                "symbol": node.name,
                "file":   node.file_path,
                "node_id": node.id,
                "is_stub": node.is_stub,
                "is_tool": node.is_tool,
            })
        except Exception:
            self._connected = False

    def emit_navigate(self, destination: str, node):
        if not self._connected:
            return
        try:
            self._sio.emit("gx_navigate", {
                "destination": destination,
                "symbol": node.name,
                "file":   node.file_path,
            })
        except Exception:
            self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected


class GraphDB:
    def __init__(self, db_path: str):
        self._path = db_path
        self._con = sqlite3.connect(db_path, check_same_thread=False)

    def top_nodes(self, limit: int) -> list[Node]:
        """Load the highest-degree nodes — best starting view of a corpus."""
        rows = self._con.execute("""
            SELECT f.id, f.name, f.file_path, f.is_stub, f.is_tool,
                   COUNT(e.id) as deg
            FROM functions f
            LEFT JOIN graph_edges e ON e.caller = f.name AND e.caller_file = f.file_path
            GROUP BY f.id
            ORDER BY deg DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [Node(r[0], r[1], r[2], bool(r[3]), bool(r[4]), r[5]) for r in rows]

    def neighbors(self, node: Node) -> tuple[list[Node], list[Edge]]:
        """Return immediate callers + callees of a node, plus edges between them."""
        # Callees (functions this node calls)
        callee_rows = self._con.execute("""
            SELECT DISTINCT f.id, f.name, f.file_path, f.is_stub, f.is_tool
            FROM graph_edges e
            JOIN functions f ON f.name = e.callee AND f.file_path = e.caller_file
            WHERE e.caller = ? AND e.caller_file = ?
            LIMIT 40
        """, (node.name, node.file_path)).fetchall()

        # Callers (functions that call this node)
        caller_rows = self._con.execute("""
            SELECT DISTINCT f.id, f.name, f.file_path, f.is_stub, f.is_tool
            FROM graph_edges e
            JOIN functions f ON f.name = e.caller AND f.file_path = e.caller_file
            WHERE e.callee = ?
            LIMIT 40
        """, (node.name,)).fetchall()

        nodes = []
        for r in callee_rows + caller_rows:
            nodes.append(Node(r[0], r[1], r[2], bool(r[3]), bool(r[4])))

        edges = []
        for n in nodes:
            edges.append(Edge(node.id, n.id))

        return nodes, edges

    def edges_for_ids(self, ids: set[int]) -> list[Edge]:
        """All edges between a given set of node ids."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._con.execute(f"""
            SELECT DISTINCT f1.id, f2.id
            FROM graph_edges e
            JOIN functions f1 ON f1.name = e.caller AND f1.file_path = e.caller_file
            JOIN functions f2 ON f2.name = e.callee AND f2.file_path = e.caller_file
            WHERE f1.id IN ({ph}) AND f2.id IN ({ph})
        """, list(ids) * 2).fetchall()
        return [Edge(r[0], r[1]) for r in rows]

    def classify_info(self, node: Node) -> str:
        """Return classify_stub verdict if available."""
        try:
            row = self._con.execute("""
                SELECT kind, subject FROM knowledge_artifacts
                WHERE kind IN ('classification','stub_classification')
                  AND subject = ?
                LIMIT 1
            """, (node.name,)).fetchone()
            if row:
                return row[0]
        except Exception:
            pass
        return ""

    def caller_count(self, node: Node) -> int:
        row = self._con.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE callee=?", (node.name,)
        ).fetchone()
        return row[0] if row else 0

    def callee_count(self, node: Node) -> int:
        row = self._con.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE caller=? AND caller_file=?",
            (node.name, node.file_path)
        ).fetchone()
        return row[0] if row else 0

    def cluster_summary(self, hub: Node, component_ids: set) -> dict:
        """Return summary data for a cluster hub panel section.

        component_ids: set of Node.id for all nodes in the hub's component.
        Returns dict with keys: files, entry_points, external_callees, summaries.
        """
        component_names: list[str] = []
        try:
            rows = self._con.execute(
                "SELECT DISTINCT name FROM functions WHERE id IN ({})".format(
                    ",".join("?" * len(component_ids))
                ),
                list(component_ids),
            ).fetchall()
            component_names = [r[0] for r in rows]
        except Exception:
            pass

        # Files in this cluster
        files: list[str] = []
        try:
            rows = self._con.execute(
                "SELECT DISTINCT file_path FROM functions WHERE id IN ({})".format(
                    ",".join("?" * len(component_ids))
                ),
                list(component_ids),
            ).fetchall()
            files = sorted(set(r[0].replace("\\", "/").split("/")[-1] for r in rows))
        except Exception:
            pass

        # Entry points: http_route or is_tool within the cluster
        entry_points: list[str] = []
        try:
            rows = self._con.execute(
                "SELECT name FROM functions WHERE id IN ({}) AND (http_route IS NOT NULL OR is_tool=1)".format(
                    ",".join("?" * len(component_ids))
                ),
                list(component_ids),
            ).fetchall()
            entry_points = [r[0].split("::")[-1] for r in rows][:8]
        except Exception:
            pass

        # External callees: edges from component to outside
        external_callees: list[str] = []
        if component_names:
            try:
                placeholders = ",".join("?" * len(component_names))
                rows = self._con.execute(
                    f"SELECT DISTINCT callee FROM graph_edges "
                    f"WHERE caller IN ({placeholders}) AND callee NOT IN ({placeholders})",
                    component_names + component_names,
                ).fetchall()
                external_callees = [r[0].split("::")[-1] for r in rows][:8]
            except Exception:
                pass

        # Semantic summary for the hub itself
        summaries: list[str] = []
        try:
            rows = self._con.execute(
                "SELECT content FROM semantic_summaries WHERE subject=? LIMIT 1",
                (hub.name,),
            ).fetchall()
            summaries = [r[0][:200] for r in rows]
        except Exception:
            pass

        return {
            "files": files[:8],
            "entry_points": entry_points,
            "external_callees": external_callees,
            "summaries": summaries,
        }

    def search(self, query: str, limit: int = 30) -> list[Node]:
        q = f"%{query}%"
        rows = self._con.execute("""
            SELECT f.id, f.name, f.file_path, f.is_stub, f.is_tool,
                   (SELECT COUNT(*) FROM graph_edges e WHERE e.caller=f.name) as deg
            FROM functions f
            WHERE f.name LIKE ?
            ORDER BY deg DESC LIMIT ?
        """, (q, limit)).fetchall()
        return [Node(r[0], r[1], r[2], bool(r[3]), bool(r[4]), r[5]) for r in rows]

    def corpus_name(self) -> str:
        try:
            row = self._con.execute(
                "SELECT value FROM project_meta WHERE key='corpus_name' LIMIT 1"
            ).fetchone()
            if row:
                return row[0]
        except Exception:
            pass
        return Path(self._path).stem


# ---------------------------------------------------------------------------
# Force-directed layout (Fruchterman-Reingold, background thread)
# ---------------------------------------------------------------------------

class Layout:
    def __init__(self):
        self._nodes: list[Node] = []
        self._adj: dict[int, set[int]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.temperature = 1.0

    def reset(self, nodes: list[Node], edges: list[Edge]):
        with self._lock:
            self._nodes = nodes
            self._adj = {n.id: set() for n in nodes}
            id_set = {n.id for n in nodes}
            for e in edges:
                if e.src_id in id_set and e.dst_id in id_set:
                    self._adj[e.src_id].add(e.dst_id)
                    self._adj[e.dst_id].add(e.src_id)
            # Place nodes in a degree-sorted spiral within the visible frame.
            # Target radius = half of the smaller viewport dimension so everything
            # starts on screen. At zoom=1 the graph area is GRAPH_W x SCREEN_H pixels.
            target_r = min(GRAPH_W, SCREEN_H) * 0.38   # ~340px for 1100x900
            n_nodes = len(nodes)
            max_i_r = math.sqrt(max(n_nodes - 1, 1))   # spiral grows as sqrt
            unplaced = [n for n in nodes if n.x == 0.0 and n.y == 0.0]
            unplaced.sort(key=lambda n: -n.degree)
            for i, n in enumerate(unplaced):
                angle = i * 2.399  # golden angle keeps neighbours apart
                r = target_r * math.sqrt(i + 1) / max_i_r
                n.x = math.cos(angle) * r + random.uniform(-3, 3)
                n.y = math.sin(angle) * r + random.uniform(-3, 3)
            # Temperature in pixel units: max displacement per step.
            # Start at ~15% of target radius so nodes settle without flying off.
            self.temperature = target_r * 0.15

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            with self._lock:
                nodes = list(self._nodes)
                adj = dict(self._adj)
                temp = self.temperature

            if not nodes or temp < 0.5:
                time.sleep(0.05)
                continue

            n = len(nodes)
            # k calibrated to the visible frame: equilibrium spacing should be
            # ~25 world units (pixels at zoom=1) so 120 nodes fit comfortably
            # in the 1100×900 viewport.
            k = 28.0
            # Gravity must satisfy: k/gravity = max desired radius from centre.
            # Target ≤ 380 world units → gravity = 28/380 ≈ 0.074.
            # This ensures no cluster drifts beyond the visible area.
            gravity = 0.074

            # Accumulate forces
            fx = {nd.id: 0.0 for nd in nodes}
            fy = {nd.id: 0.0 for nd in nodes}

            # Repulsion (all pairs — O(n²), fine for ≤200 nodes)
            for i in range(n):
                for j in range(i + 1, n):
                    a, b = nodes[i], nodes[j]
                    dx, dy = a.x - b.x, a.y - b.y
                    dist = math.sqrt(dx*dx + dy*dy) or 0.01
                    rep = (k * k) / dist
                    fx[a.id] += (dx / dist) * rep
                    fy[a.id] += (dy / dist) * rep
                    fx[b.id] -= (dx / dist) * rep
                    fy[b.id] -= (dy / dist) * rep

            # Attraction (edges)
            for nd in nodes:
                for nbr_id in adj.get(nd.id, set()):
                    nbr = next((x for x in nodes if x.id == nbr_id), None)
                    if not nbr:
                        continue
                    dx, dy = nd.x - nbr.x, nd.y - nbr.y
                    dist = math.sqrt(dx*dx + dy*dy) or 0.01
                    att = (dist * dist) / k
                    fx[nd.id] -= (dx / dist) * att
                    fy[nd.id] -= (dy / dist) * att

            # Centre gravity — pulls all nodes toward (0,0).
            # Strength tuned so equilibrium radius = k/gravity ≈ 380 world units,
            # which fits inside the 1100×900 viewport at zoom≈0.5.
            for nd in nodes:
                fx[nd.id] -= nd.x * gravity
                fy[nd.id] -= nd.y * gravity

            # Apply with temperature cap
            with self._lock:
                for nd in self._nodes:
                    mag = math.sqrt(fx[nd.id]**2 + fy[nd.id]**2) or 1.0
                    disp = min(mag, temp)
                    nd.x += (fx[nd.id] / mag) * disp
                    nd.y += (fy[nd.id] / mag) * disp
                self.temperature *= 0.90

            time.sleep(1 / 60)


# ---------------------------------------------------------------------------
# Main explorer app
# ---------------------------------------------------------------------------

class GraphExplorer:
    def __init__(self, db_path: str):
        self._db = GraphDB(db_path)
        self._layout = Layout()
        self._nodes: list[Node] = []
        self._edges: list[Edge] = []
        self._node_map: dict[int, Node] = {}
        self._selected: Optional[Node] = None
        self._expanded: Optional[Node] = None   # node we double-clicked into
        self._callers_of_sel: set[int] = set()
        self._callees_of_sel: set[int] = set()
        self._search_text = ""
        self._search_active = False
        self._search_results: list[Node] = []
        self._last_click_node: Optional[Node] = None
        self._last_click_time: float = 0.0
        self._inspect_scroll = 0
        self._status = "Loading…"
        self._text_scale_idx: int = TEXT_SCALE_DEFAULT
        self._clusters: list[Node] = []   # hub node per connected component
        self._cluster_hit_rows: list[tuple[int, int, Node]] = []  # (y0, y1, node)
        self._cluster_scroll: int = 0   # index of first visible cluster row
        self._minimap_geo = None        # set by _draw_minimap each frame
        self._minimap_dragging = False  # dragging the viewport box in minimap
        self._pending_frame_id: Optional[int] = None  # frame this node after next layout settle
        self._search_bar_rect = (0, 0, 0, 0)   # (x, y, w, h) in screen coords
        self._search_result_rects: list[tuple[int,int,int,int,Node]] = []  # (x,y,w,h,node)
        self._bridge = _SocketBridge()
        self._ctx_menu: Optional[dict] = None   # {node, items, x, y, rects}
        self._action_btn_rects: list[tuple] = []  # (x,y,w,h,dest)
        self._cluster_summary: Optional[dict] = None   # cached for selected hub
        self._cluster_summary_for: Optional[int] = None  # node id it was built for

    # ------------------------------------------------------------------
    # Graph loading
    # ------------------------------------------------------------------

    def _load_top(self):
        self._status = "Loading top nodes…"
        nodes = self._db.top_nodes(MAX_INITIAL_NODES)
        # Compute inter-edges
        ids = {n.id for n in nodes}
        edges = self._db.edges_for_ids(ids)
        # Degree from edges
        deg: dict[int, int] = {n.id: 0 for n in nodes}
        for e in edges:
            deg[e.src_id] = deg.get(e.src_id, 0) + 1
            deg[e.dst_id] = deg.get(e.dst_id, 0) + 1
        for n in nodes:
            n.degree = deg.get(n.id, n.degree)
        self._nodes = nodes
        self._edges = edges
        self._node_map = {n.id: n for n in nodes}
        self._layout.reset(nodes, edges)
        self._layout.start()
        self._clusters = self._find_cluster_hubs()
        self._cluster_scroll = 0
        corpus = self._db.corpus_name()
        self._status = f"{corpus}  ·  {len(nodes)} nodes  ·  {len(edges)} edges shown"

    def _find_cluster_hubs(self) -> list[Node]:
        """BFS connected components; return highest-degree node per component."""
        adj: dict[int, set[int]] = {n.id: set() for n in self._nodes}
        for e in self._edges:
            adj[e.src_id].add(e.dst_id)
            adj[e.dst_id].add(e.src_id)
        visited: set[int] = set()
        hubs: list[Node] = []
        for start in self._nodes:
            if start.id in visited:
                continue
            component: list[Node] = []
            queue = [start]
            visited.add(start.id)
            while queue:
                cur = queue.pop()
                component.append(cur)
                for nbr_id in adj.get(cur.id, set()):
                    if nbr_id not in visited:
                        visited.add(nbr_id)
                        nbr = self._node_map.get(nbr_id)
                        if nbr:
                            queue.append(nbr)
            hub = max(component, key=lambda n: n.degree)
            hubs.append(hub)
        hubs.sort(key=lambda n: -n.degree)
        return hubs

    def _expand_node(self, node: Node):
        """Show only the node and its immediate neighbors."""
        neighbors, _ = self._db.neighbors(node)
        # Merge with current visible if we already have them
        existing_ids = {n.id for n in self._nodes}
        new_nodes = [n for n in neighbors if n.id not in existing_ids]
        # Position new nodes around the expanded node
        for i, n in enumerate(new_nodes):
            angle = 2 * math.pi * i / max(len(new_nodes), 1)
            r = 120 + random.uniform(-20, 20)
            n.x = node.x + math.cos(angle) * r
            n.y = node.y + math.sin(angle) * r

        all_nodes = self._nodes + new_nodes
        all_ids = {n.id for n in all_nodes}
        edges = self._db.edges_for_ids(all_ids)

        self._nodes = all_nodes
        self._edges = edges
        self._node_map = {n.id: n for n in all_nodes}
        self._expanded = node
        self._layout.reset(all_nodes, edges)
        self._status = f"Expanded: {node.short_name}  ·  {len(all_nodes)} nodes"

    def _select_node(self, node: Node):
        self._selected = node
        # Find which neighbors are callers vs callees
        neighbors, _ = self._db.neighbors(node)
        nbr_ids = {n.id for n in neighbors}
        # Edges from selected = callees; edges to selected = callers
        self._callers_of_sel = set()
        self._callees_of_sel = set()
        for e in self._edges:
            if e.src_id == node.id and e.dst_id in self._node_map:
                self._callees_of_sel.add(e.dst_id)
            if e.dst_id == node.id and e.src_id in self._node_map:
                self._callers_of_sel.add(e.src_id)
        self._inspect_scroll = 0
        self._bridge.emit_select(node)
        # Rebuild cluster summary if this node is a hub (or clear it)
        hub_ids = {h.id for h in self._clusters}
        if node.id in hub_ids and node.id != self._cluster_summary_for:
            if self._expanded:
                # Expanded view mixes multiple neighborhoods; walk only the hub's component.
                _adj: dict[int, set[int]] = {}
                for e in self._edges:
                    _adj.setdefault(e.src_id, set()).add(e.dst_id)
                    _adj.setdefault(e.dst_id, set()).add(e.src_id)
                _vis: set[int] = {node.id}
                _q = [node.id]
                while _q:
                    _cur = _q.pop()
                    for _nbr in _adj.get(_cur, set()):
                        if _nbr not in _vis:
                            _vis.add(_nbr)
                            _q.append(_nbr)
                component_ids = _vis
            else:
                component_ids = {n.id for n in self._nodes}
            self._cluster_summary = self._db.cluster_summary(node, component_ids)
            self._cluster_summary_for = node.id
        elif node.id not in hub_ids:
            self._cluster_summary = None
            self._cluster_summary_for = None

    def _navigate_to(self, destination: str, node: Node):
        """Route node to a UI surface or local action."""
        if destination == "editor":
            row = self._db._con.execute(
                "SELECT line_number FROM functions WHERE name=? AND file_path=?",
                (node.name, node.file_path)
            ).fetchone()
            line = row[0] if row and row[0] else 1
            try:
                subprocess.Popen(["code", "--goto", f"{node.file_path}:{line}"])
            except FileNotFoundError:
                pass  # VS Code not on PATH — silently ignore
        elif destination == "expand":
            self._expand_node(node)
            self._select_node(node)
            if hasattr(self, "_cam"):
                self._frame_node(self._cam, node)
        elif destination == "frame":
            self._select_node(node)
            if hasattr(self, "_cam"):
                self._frame_node(self._cam, node)
        elif destination == "copy_name":
            try:
                import pyperclip
                pyperclip.copy(node.name)
            except Exception:
                pass
        elif destination == "copy_path":
            try:
                import pyperclip
                pyperclip.copy(node.file_path)
            except Exception:
                pass
        else:
            # workbench / oracle / map / call_tree — bridge to UI
            self._bridge.emit_navigate(destination, node)

    # ------------------------------------------------------------------
    # Camera helpers
    # ------------------------------------------------------------------

    def _make_camera(self):
        cam = ffi.new('Camera2D *')
        cam.target.x = 0.0
        cam.target.y = 0.0
        cam.offset.x = GRAPH_W / 2.0
        cam.offset.y = SCREEN_H / 2.0
        cam.rotation = 0.0
        cam.zoom = 1.0
        return cam

    def _screen_to_world(self, cam, sx, sy):
        wp = rl.GetScreenToWorld2D(_v2(sx, sy), cam[0])
        return wp.x, wp.y

    def _world_to_screen(self, cam, wx, wy):
        sp = rl.GetWorldToScreen2D(_v2(wx, wy), cam[0])
        return sp.x, sp.y

    def _node_at(self, cam, sx, sy) -> Optional[Node]:
        wx, wy = self._screen_to_world(cam, sx, sy)
        best, best_d = None, 1e9
        for n in self._nodes:
            dx, dy = n.x - wx, n.y - wy
            d = math.sqrt(dx*dx + dy*dy)
            if d < n.radius + 4 and d < best_d:
                best, best_d = n, d
        return best

    def _frame_all(self, cam):
        if not self._nodes:
            return
        xs = [n.x for n in self._nodes]
        ys = [n.y for n in self._nodes]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        span_x = max(xs) - min(xs) + 100
        span_y = max(ys) - min(ys) + 100
        zoom = min(GRAPH_W / max(span_x, 1), SCREEN_H / max(span_y, 1)) * 0.85
        cam.zoom = max(0.05, min(zoom, 4.0))
        cam.target.x = cx
        cam.target.y = cy
        cam.offset.x = GRAPH_W / 2.0
        cam.offset.y = SCREEN_H / 2.0

    def _frame_node(self, cam, node: Node):
        cam.target.x = node.x
        cam.target.y = node.y
        cam.zoom = max(cam.zoom, 1.2)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_edge(self, cam, e: Edge, highlight: bool):
        src = self._node_map.get(e.src_id)
        dst = self._node_map.get(e.dst_id)
        if not src or not dst:
            return
        if highlight:
            col = _col(*COL_EDGE_SEL)
        else:
            col = _col(*COL_EDGE_NORMAL)
        rl.DrawLineV(_v2(src.x, src.y), _v2(dst.x, dst.y), col)

    def _node_color(self, node: Node) -> tuple:
        if self._selected:
            if node.id == self._selected.id:
                return COL_NODE_SEL
            if node.id in self._callers_of_sel:
                return COL_NODE_CALLER
            if node.id in self._callees_of_sel:
                return COL_NODE_CALLEE
            if self._expanded and node.id != self._expanded.id:
                return COL_NODE_FADED
        return node.color

    def _draw_node(self, node: Node, cam=None):
        col = self._node_color(node)
        r = node.radius
        is_sel = self._selected and node.id == self._selected.id
        if is_sel:
            # Gold halo → white ring → node on top, so selection is clear at any zoom
            rl.DrawCircleV(_v2(node.x, node.y), r + 7, _col(255, 215, 0, 160))
            rl.DrawCircleV(_v2(node.x, node.y), r + 4, _col(255, 255, 255, 230))
        rl.DrawCircleV(_v2(node.x, node.y), r, _col(*col))
        if is_sel:
            rl.DrawCircleLinesV(_v2(node.x, node.y), r - 1, _col(255, 255, 255, 180))

    def _draw_text(self, text: str, x: int, y: int, size: int, color: tuple):
        """Draw text using the loaded font if available, else raylib default."""
        col = _col(*color)
        if self._font:
            spacing = size * 0.05
            rl.DrawTextEx(self._font, text.encode(), _v2(x, y),
                          float(size), spacing, col)
        else:
            rl.DrawText(text.encode(), x, y, size, col)

    def _measure_text(self, text: str, size: int) -> int:
        if self._font:
            spacing = size * 0.05
            v = rl.MeasureTextEx(self._font, text.encode(), float(size), spacing)
            return int(v.x)
        return rl.MeasureText(text.encode(), size)

    def _draw_label(self, cam, node: Node):
        sx, sy = self._world_to_screen(cam, node.x, node.y)
        if sx < -20 or sx > GRAPH_W + 20 or sy < -20 or sy > SCREEN_H + 20:
            return
        label = node.short_name
        if len(label) > 22:
            label = label[:20] + "…"
        fs = 11
        tw = self._measure_text(label, fs)
        lx = int(sx - tw / 2)
        ly = int(sy + node.radius * cam.zoom + 3)
        self._draw_text(label, lx, ly, fs, COL_TEXT_DIM)

    @staticmethod
    def _ctx_menu_total_h() -> int:
        return sum(_CTX_MENU_DIV if it is None else _CTX_MENU_H for it in _CTX_MENU_ITEMS) + 8

    @staticmethod
    def _ctx_menu_clamped(raw_x: int, raw_y: int):
        total_h = GraphExplorer._ctx_menu_total_h()
        cx = min(raw_x, SCREEN_W - _CTX_MENU_W - 4)
        cy = min(raw_y, SCREEN_H - total_h - 4)
        return cx, cy

    def _draw_ctx_menu(self, cm: dict):
        cm_fs = 11
        total_h = self._ctx_menu_total_h()
        cx, cy = cm["cx"], cm["cy"]
        # Shadow + background
        rl.DrawRectangle(cx + 3, cy + 3, _CTX_MENU_W, total_h, _col(0, 0, 0, 120))
        rl.DrawRectangle(cx, cy, _CTX_MENU_W, total_h, _col(30, 33, 45, 240))
        rl.DrawRectangleLines(cx, cy, _CTX_MENU_W, total_h, _col(80, 90, 130, 200))
        iy = cy + 4
        mx, my = int(rl.GetMouseX()), int(rl.GetMouseY())
        for item in _CTX_MENU_ITEMS:
            if item is None:
                rl.DrawLine(cx + 6, iy + 3, cx + _CTX_MENU_W - 6, iy + 3, _col(60, 65, 90, 200))
                iy += _CTX_MENU_DIV
                continue
            lbl, dest = item
            hovered = cx <= mx <= cx + _CTX_MENU_W and iy <= my <= iy + _CTX_MENU_H
            if hovered:
                rl.DrawRectangle(cx + 2, iy, _CTX_MENU_W - 4, _CTX_MENU_H, _col(60, 80, 160, 180))
            self._draw_text(lbl, cx + 10, iy + (_CTX_MENU_H - cm_fs) // 2, cm_fs, COL_TEXT)
            iy += _CTX_MENU_H

    def _draw_minimap(self, cam):
        if not self._nodes:
            self._minimap_geo = None
            return
        xs = [n.x for n in self._nodes]
        ys = [n.y for n in self._nodes]
        mn_x, mx_x = min(xs), max(xs)
        mn_y, mx_y = min(ys), max(ys)
        w_span = max(mx_x - mn_x, 1)
        h_span = max(mx_y - mn_y, 1)

        mx0 = GRAPH_W - MINIMAP_W - MINIMAP_MARGIN
        my0 = SCREEN_H - MINIMAP_H - MINIMAP_MARGIN

        # Store geometry for hit-testing in the input loop
        self._minimap_geo = (mx0, my0, mn_x, mn_y, w_span, h_span)

        rl.DrawRectangle(mx0, my0, MINIMAP_W, MINIMAP_H, _col(*COL_MINIMAP_BG))
        rl.DrawRectangleLines(mx0, my0, MINIMAP_W, MINIMAP_H, _col(*COL_PANEL_BORDER))

        def world_to_mini(wx, wy):
            px = mx0 + int((wx - mn_x) / w_span * MINIMAP_W)
            py = my0 + int((wy - mn_y) / h_span * MINIMAP_H)
            return px, py

        for n in self._nodes:
            mpx, mpy = world_to_mini(n.x, n.y)
            col = self._node_color(n)
            rl.DrawCircle(mpx, mpy, 2, _col(*col))

        # Viewport rectangle
        tl_x, tl_y = self._screen_to_world(cam, 0, 0)
        br_x, br_y = self._screen_to_world(cam, GRAPH_W, SCREEN_H)
        vx0, vy0 = world_to_mini(tl_x, tl_y)
        vx1, vy1 = world_to_mini(br_x, br_y)
        vw, vh = max(vx1 - vx0, 2), max(vy1 - vy0, 2)
        rl.DrawRectangleLines(vx0, vy0, vw, vh, _col(*COL_MINIMAP_VP))

    def _draw_panel(self):
        px = GRAPH_W
        ts = TEXT_SCALE_STEPS[self._text_scale_idx]
        rl.DrawRectangle(px, 0, PANEL_W, SCREEN_H, _col(*COL_PANEL_BG))
        rl.DrawRectangle(px, 0, 1, SCREEN_H, _col(*COL_PANEL_BORDER))

        y = 10
        def line(text, color=COL_TEXT, fs=11, indent=0):
            nonlocal y
            scaled = max(8, int(fs * ts))
            self._draw_text(text, px + 12 + indent, y, scaled, color)
            y += scaled + 5

        def divider():
            nonlocal y
            y += 4
            rl.DrawRectangle(px + 12, y, PANEL_W - 24, 1, _col(*COL_PANEL_BORDER))
            y += 6

        # --- Cluster hubs (scrollable) ---
        self._cluster_hit_rows = []
        row_h = max(8, int(10 * ts)) + 5
        # Reserve space: clusters get up to 40% of panel height, rest for details+controls
        cluster_max_h = int(SCREEN_H * 0.40)
        max_visible = max(3, cluster_max_h // row_h)
        n_clusters = len(self._clusters)
        # Clamp scroll
        self._cluster_scroll = max(0, min(self._cluster_scroll, max(0, n_clusters - max_visible)))
        scroll = self._cluster_scroll
        visible = self._clusters[scroll: scroll + max_visible]

        hdr_fs = max(8, int(11 * ts))
        hdr_label = f"Clusters  ({n_clusters})"
        self._draw_text(hdr_label, px + 12, y, hdr_fs, COL_TEXT)
        # Scroll hint on same line
        if n_clusters > max_visible:
            hint = "wheel to scroll"
            hw = self._measure_text(hint, max(7, int(8 * ts)))
            self._draw_text(hint, px + PANEL_W - hw - 12, y, max(7, int(8 * ts)), COL_TEXT_DIM)
        y += hdr_fs + 5
        divider()

        if scroll > 0:
            self._draw_text(f"  ^ {scroll} above", px + 12, y, max(7, int(8 * ts)), COL_TEXT_DIM)
            y += max(7, int(8 * ts)) + 3

        for hub in visible:
            is_sel = self._selected and self._selected.id == hub.id
            col = (255, 220, 80, 255) if is_sel else (
                COL_NODE_TOOL if hub.is_tool else (COL_NODE_STUB if hub.is_stub else COL_TEXT))
            row_y0 = y
            label = hub.short_name
            self._draw_text(f"  {label}  ({hub.degree})", px + 12, y, max(8, int(10 * ts)), col)
            y += row_h
            self._cluster_hit_rows.append((row_y0, y, hub))

        remaining = n_clusters - scroll - len(visible)
        if remaining > 0:
            self._draw_text(f"  v {remaining} below", px + 12, y, max(7, int(8 * ts)), COL_TEXT_DIM)
            y += max(7, int(8 * ts)) + 3

        divider()

        # --- Search bar (always visible in panel) ---
        sb_x = px + 8
        sb_w = PANEL_W - 16
        sb_h = max(20, int(22 * ts))
        self._search_bar_rect = (sb_x, y, sb_w, sb_h)
        active_col = (100, 140, 220, 255) if self._search_active else _col(*COL_SEARCH_BDR)
        rl.DrawRectangle(sb_x, y, sb_w, sb_h, _col(*COL_SEARCH_BG))
        rl.DrawRectangleLines(sb_x, y, sb_w, sb_h, active_col)
        prompt = self._search_text if self._search_text else ("Search nodes…" if not self._search_active else "")
        cursor = "_" if self._search_active and int(time.time() * 2) % 2 == 0 else ""
        txt_col = COL_TEXT if self._search_text else COL_TEXT_DIM
        txt_fs = max(8, int(10 * ts))
        self._draw_text(prompt + cursor, sb_x + 6, y + (sb_h - txt_fs) // 2, txt_fs, txt_col)
        y += sb_h + 4

        self._search_result_rects = []
        if self._search_results:
            for nd in self._search_results[:6]:
                rh = max(28, int(30 * ts))
                rl.DrawRectangle(sb_x, y, sb_w, rh, _col(30, 33, 46, 240))
                rl.DrawRectangleLines(sb_x, y, sb_w, rh, _col(*COL_PANEL_BORDER))
                r_col = COL_NODE_STUB if nd.is_stub else COL_TEXT
                # Name on first line
                name_fs = max(8, int(10 * ts))
                name_lbl = nd.name if len(nd.name) < 30 else nd.name[:28] + "~"
                self._draw_text(name_lbl, sb_x + 6, y + 4, name_fs, r_col)
                # File on second line in dimmer smaller text
                fname = nd.file_path.replace("\\", "/").split("/")[-1]
                file_fs = max(7, int(8 * ts))
                self._draw_text(fname, sb_x + 6, y + 4 + name_fs + 2, file_fs, COL_TEXT_DIM)
                self._search_result_rects.append((sb_x, y, sb_w, rh, nd))
                y += rh
            y += 4

        divider()

        # --- Selected node details ---
        if self._selected:
            nd = self._selected
            line(nd.short_name, COL_TEXT, 13)
            line(nd.name, COL_TEXT_DIM, 9)
            y += 2

            tags = []
            if nd.is_stub: tags.append(("STUB", COL_NODE_STUB))
            if nd.is_tool: tags.append(("TOOL", COL_NODE_TOOL))
            tx = px + 12
            for tag, tc in tags:
                tw = self._measure_text(tag, max(8, int(10 * ts)))
                rl.DrawRectangle(tx, y, tw + 8, int(16 * ts), _col(*tc))
                self._draw_text(tag, tx + 4, y + 3, max(8, int(10 * ts)), (20, 20, 20, 255))
                tx += tw + 12
            if tags:
                y += int(22 * ts)

            fp = nd.file_path.replace("\\", "/")
            parts = fp.split("/")
            short_fp = "/".join(parts[-2:]) if len(parts) > 1 else fp
            line(short_fp, COL_TEXT_DIM, 9)
            y += 2

            callers = self._db.caller_count(nd)
            callees = self._db.callee_count(nd)
            line(f"^ {callers} callers   v {callees} callees", COL_TEXT, 10)
            y += 2

            if self._callers_of_sel:
                line(f"Callers in view ({len(self._callers_of_sel)}):", COL_NODE_CALLER, 10)
                for nid in list(self._callers_of_sel)[:5]:
                    n2 = self._node_map.get(nid)
                    if n2:
                        line(f"  {n2.short_name}", COL_TEXT_DIM, 9, 4)
            if self._callees_of_sel:
                line(f"Calls in view ({len(self._callees_of_sel)}):", COL_NODE_CALLEE, 10)
                for nid in list(self._callees_of_sel)[:5]:
                    n2 = self._node_map.get(nid)
                    if n2:
                        line(f"  {n2.short_name}", COL_TEXT_DIM, 9, 4)

            # --- Cluster summary (hub nodes only) ---
            cs = self._cluster_summary
            if cs and self._cluster_summary_for == nd.id:
                y += 4
                divider()
                line("Cluster summary", COL_TEXT, 10)
                if cs["files"]:
                    line("Files:", COL_TEXT_DIM, 9)
                    for f in cs["files"][:6]:
                        line(f"  {f}", COL_TEXT_DIM, 8, 4)
                if cs["entry_points"]:
                    y += 2
                    line("Entry points:", COL_TEXT_DIM, 9)
                    for ep in cs["entry_points"][:5]:
                        line(f"  {ep}", (120, 200, 120, 255), 8, 4)
                if cs["external_callees"]:
                    y += 2
                    line("External callees:", COL_TEXT_DIM, 9)
                    for ec in cs["external_callees"][:5]:
                        line(f"  {ec}", COL_TEXT_DIM, 8, 4)
                if cs["summaries"]:
                    y += 2
                    line("Summary:", COL_TEXT_DIM, 9)
                    # Wrap at ~32 chars to fit panel width
                    text = cs["summaries"][0]
                    words = text.split()
                    cur_line = ""
                    for w in words:
                        if len(cur_line) + len(w) + 1 > 32:
                            line(f"  {cur_line.strip()}", COL_TEXT_DIM, 8, 4)
                            cur_line = w + " "
                        else:
                            cur_line += w + " "
                    if cur_line.strip():
                        line(f"  {cur_line.strip()}", COL_TEXT_DIM, 8, 4)

            # --- Navigation action buttons ---
            y += 4
            btn_labels = ["Workbench", "Oracle", "Map", "Call Tree", "Editor"]
            btn_dests  = ["workbench", "oracle",  "map", "call_tree", "editor"]
            btn_fs = max(8, int(10 * ts))
            btn_h  = int(22 * ts)
            btn_margin = 4
            bx = px + 12
            brow_y = y
            self._action_btn_rects = []
            for lbl, dest in zip(btn_labels, btn_dests):
                bw = self._measure_text(lbl, btn_fs) + 10
                if bx + bw > px + PANEL_W - 12:
                    bx = px + 12
                    brow_y += btn_h + btn_margin
                bg = (60, 90, 160, 200) if dest != "editor" else (60, 130, 80, 200)
                rl.DrawRectangle(bx, brow_y, bw, btn_h, _col(*bg))
                self._draw_text(lbl, bx + 5, brow_y + (btn_h - btn_fs) // 2, btn_fs, COL_TEXT)
                self._action_btn_rects.append((bx, brow_y, bw, btn_h, dest))
                bx += bw + btn_margin
            y = brow_y + btn_h + 6
            divider()
        else:
            line("Click a node to inspect", COL_TEXT_DIM, 10)
            divider()

        # --- Controls at bottom ---
        bottom_y = SCREEN_H - MINIMAP_H - MINIMAP_MARGIN - int(160 * ts) - 10
        y = max(y, bottom_y)
        line(self._status, COL_TEXT_DIM, 9)
        divider()
        line("Controls", COL_TEXT, 10)
        for tip in [
            "Scroll — zoom on cursor",
            "Drag — pan",
            "Click — select",
            "Dbl-click — expand",
            "F — frame   Esc — clear",
            "/ — search   +/- text size",
        ]:
            line(tip, COL_TEXT_DIM, 9, 4)


    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        rl.SetConfigFlags(rl.FLAG_WINDOW_RESIZABLE)
        rl.InitWindow(SCREEN_W, SCREEN_H,
                      b"Determined \xe2\x80\x94 Graph Explorer")
        rl.SetTargetFPS(FPS)

        # Load font — Segoe UI if available, else raylib default
        self._font = None
        if _FONT_AVAILABLE:
            self._font = rl.LoadFontEx(_FONT_PATH.encode(), 18, ffi.NULL, 0)
            rl.SetTextureFilter(self._font.texture, rl.TEXTURE_FILTER_BILINEAR)

        cam = self._make_camera()
        self._cam = cam  # expose to _navigate_to for frame/expand actions

        # Load graph in background so window appears immediately
        t = threading.Thread(target=self._load_top, daemon=True)
        t.start()

        panning = False
        pan_start_mouse = (0.0, 0.0)
        pan_start_target = (0.0, 0.0)
        framed = False
        last_framed_node_count = 0

        while not rl.WindowShouldClose():
            dt = rl.GetFrameTime()
            mx = rl.GetMouseX()
            my = rl.GetMouseY()
            in_graph = mx < GRAPH_W

            # --- Input ---

            # Zoom centered on cursor.
            # cam.offset is fixed at (GRAPH_W/2, SCREEN_H/2) throughout.
            # To keep the world point under the cursor stationary after a zoom:
            #   target_new = world_under_cursor - (cursor - offset) / new_zoom
            if in_graph:
                wheel = rl.GetMouseWheelMove()
                if wheel != 0:
                    wp = rl.GetScreenToWorld2D(_v2(mx, my), cam[0])
                    factor = 1.12 if wheel > 0 else 1 / 1.12
                    new_zoom = max(ZOOM_MIN, min(cam.zoom * factor, ZOOM_MAX))
                    cam.zoom = new_zoom
                    cam.target.x = wp.x - (mx - cam.offset.x) / new_zoom
                    cam.target.y = wp.y - (my - cam.offset.y) / new_zoom

            # Pan (left drag on empty space or middle drag)
            lmb = rl.IsMouseButtonDown(rl.MOUSE_BUTTON_LEFT)
            mmb = rl.IsMouseButtonDown(rl.MOUSE_BUTTON_MIDDLE)

            if (lmb or mmb) and in_graph and not panning:
                hit = self._node_at(cam, mx, my)
                if hit is None or mmb:
                    panning = True
                    pan_start_mouse = (float(mx), float(my))
                    pan_start_target = (cam.target.x, cam.target.y)

            if panning:
                if lmb or mmb:
                    dx = (float(mx) - pan_start_mouse[0]) / cam.zoom
                    dy = (float(my) - pan_start_mouse[1]) / cam.zoom
                    cam.target.x = pan_start_target[0] - dx
                    cam.target.y = pan_start_target[1] - dy
                else:
                    panning = False

            # Click / double-click
            if rl.IsMouseButtonPressed(rl.MOUSE_BUTTON_LEFT) and in_graph and not panning:
                now = time.time()
                hit = self._node_at(cam, mx, my)
                if hit:
                    dbl = (hit == self._last_click_node and now - self._last_click_time < 0.35)
                    self._last_click_node = hit
                    self._last_click_time = now
                    if dbl:
                        self._expand_node(hit)
                        self._select_node(hit)
                        self._frame_node(cam, hit)
                    else:
                        self._select_node(hit)
                else:
                    self._selected = None
                    self._callers_of_sel.clear()
                    self._callees_of_sel.clear()
                    self._last_click_node = None

            # Panel scroll (mouse wheel over panel area)
            if not in_graph:
                pwheel = rl.GetMouseWheelMove()
                if pwheel != 0:
                    self._cluster_scroll -= int(pwheel)  # wheel up = scroll list up

            # Minimap drag — click/drag anywhere in minimap to pan the main view
            geo = self._minimap_geo
            if geo:
                mm_x0, mm_y0, mn_wx, mn_wy, w_span, h_span = geo
                in_mini = (mm_x0 <= mx <= mm_x0 + MINIMAP_W and
                           mm_y0 <= my <= mm_y0 + MINIMAP_H)
                lmb = rl.IsMouseButtonDown(rl.MOUSE_BUTTON_LEFT)
                if in_mini and lmb:
                    self._minimap_dragging = True
                if not lmb:
                    self._minimap_dragging = False
                if self._minimap_dragging and geo:
                    # Map minimap pixel → world coordinate → set camera target
                    frac_x = (mx - mm_x0) / MINIMAP_W
                    frac_y = (my - mm_y0) / MINIMAP_H
                    cam.target.x = mn_wx + frac_x * w_span
                    cam.target.y = mn_wy + frac_y * h_span

            # Search bar click (panel area)
            if rl.IsMouseButtonPressed(rl.MOUSE_BUTTON_LEFT) and not in_graph:
                sbx, sby, sbw, sbh = self._search_bar_rect
                if sbx <= mx <= sbx + sbw and sby <= my <= sby + sbh:
                    self._search_active = True

            # Cluster hub click (panel area)
            if rl.IsMouseButtonPressed(rl.MOUSE_BUTTON_LEFT) and not in_graph:
                for y0, y1, hub in self._cluster_hit_rows:
                    if y0 <= my <= y1:
                        if hub.id in self._node_map:
                            self._select_node(self._node_map[hub.id])
                            self._frame_node(cam, self._node_map[hub.id])
                        break

            # Action button clicks (panel navigation buttons)
            if rl.IsMouseButtonPressed(rl.MOUSE_BUTTON_LEFT) and self._selected and self._action_btn_rects:
                for bx, by, bw, bh, dest in self._action_btn_rects:
                    if bx <= mx <= bx + bw and by <= my <= by + bh:
                        self._navigate_to(dest, self._selected)
                        break

            # Right-click on node → context menu
            if rl.IsMouseButtonPressed(rl.MOUSE_BUTTON_RIGHT):
                if in_graph:
                    hit = self._node_at(cam, mx, my)
                    if hit:
                        self._select_node(hit)
                        cx, cy = self._ctx_menu_clamped(mx, my)
                        self._ctx_menu = {"node": hit, "x": mx, "y": my, "cx": cx, "cy": cy}
                elif self._selected:
                    # Right-click in panel on selected details area
                    cx, cy = self._ctx_menu_clamped(mx, my)
                    self._ctx_menu = {"node": self._selected, "x": mx, "y": my, "cx": cx, "cy": cy}

            # Context menu hit-test on left-click; always clears menu afterward
            if self._ctx_menu and rl.IsMouseButtonPressed(rl.MOUSE_BUTTON_LEFT):
                cm = self._ctx_menu
                cx, cy = cm["cx"], cm["cy"]
                iy = cy + 4
                for item in _CTX_MENU_ITEMS:
                    if item is None:
                        iy += _CTX_MENU_DIV
                        continue
                    lbl, dest = item
                    if cx <= mx <= cx + _CTX_MENU_W and iy <= my <= iy + _CTX_MENU_H:
                        self._navigate_to(dest, cm["node"])
                        break
                    iy += _CTX_MENU_H
                self._ctx_menu = None

            # Search result click (hit-test against rects recorded during draw)
            if rl.IsMouseButtonPressed(rl.MOUSE_BUTTON_LEFT) and self._search_result_rects:
                for rx, ry, rw, rh, nd in self._search_result_rects:
                    if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                        if nd.id in self._node_map:
                            self._select_node(self._node_map[nd.id])
                            self._frame_node(cam, self._node_map[nd.id])
                        else:
                            # Bring neighborhood into view without dimming.
                            # Layout will restart; defer frame to after it settles.
                            self._expand_node(nd)
                            self._expanded = None
                            self._select_node(nd)
                            self._pending_frame_id = nd.id
                        self._search_results = []
                        self._search_result_rects = []
                        self._search_active = False
                        self._search_text = ""
                        break

            # Keyboard
            if rl.IsKeyPressed(rl.KEY_ESCAPE):
                if self._search_active:
                    self._search_active = False
                    self._search_text = ""
                    self._search_results = []
                elif self._expanded:
                    # Restore top view
                    self._expanded = None
                    self._selected = None
                    self._load_top()
                else:
                    self._selected = None
                    self._callers_of_sel.clear()
                    self._callees_of_sel.clear()

            if rl.IsKeyPressed(rl.KEY_F):
                if self._selected:
                    self._frame_node(cam, self._selected)
                else:
                    self._frame_all(cam)

            # Ctrl+0 = reset
            if rl.IsKeyDown(rl.KEY_LEFT_CONTROL) and rl.IsKeyPressed(rl.KEY_ZERO):
                self._frame_all(cam)

            # Text size: + / -
            if rl.IsKeyPressed(rl.KEY_EQUAL):   # = / + (unshifted)
                self._text_scale_idx = min(self._text_scale_idx + 1, len(TEXT_SCALE_STEPS) - 1)
            if rl.IsKeyPressed(rl.KEY_MINUS):
                self._text_scale_idx = max(self._text_scale_idx - 1, 0)

            # Search
            if rl.IsKeyPressed(rl.KEY_SLASH):
                self._search_active = True

            if self._search_active:
                key = rl.GetCharPressed()
                while key > 0:
                    if 32 <= key <= 125:
                        self._search_text += chr(key)
                    key = rl.GetCharPressed()
                if rl.IsKeyPressed(rl.KEY_BACKSPACE) and self._search_text:
                    self._search_text = self._search_text[:-1]
                if self._search_text:
                    self._search_results = self._db.search(self._search_text)
                else:
                    self._search_results = []
                # Enter — jump to first result
                if rl.IsKeyPressed(rl.KEY_ENTER) and self._search_results:
                    nd = self._search_results[0]
                    if nd.id in self._node_map:
                        self._select_node(self._node_map[nd.id])
                        self._frame_node(cam, self._node_map[nd.id])
                    else:
                        self._expand_node(nd)
                        self._expanded = None
                        self._select_node(nd)
                        self._pending_frame_id = nd.id
                    self._search_active = False
                    self._search_text = ""
                    self._search_results = []
                    self._search_result_rects = []

            # Auto-frame after each load, then hard-freeze the layout so zoom
            # is purely a camera scale — nodes never drift while zooming.
            cur_count = len(self._nodes)
            if cur_count != last_framed_node_count:
                framed = False  # new set of nodes needs framing
            if not framed and cur_count > 0 and self._layout.temperature < 3:
                self._layout.temperature = 0.0  # hard freeze
                if self._pending_frame_id and self._pending_frame_id in self._node_map:
                    self._frame_node(cam, self._node_map[self._pending_frame_id])
                    self._pending_frame_id = None
                else:
                    self._frame_all(cam)
                framed = True
                last_framed_node_count = cur_count

            # Bridge: UI asked us to highlight a symbol
            hl = self._bridge._pending_highlight
            if hl:
                self._bridge._pending_highlight = None
                results = self._db.search(hl)
                if results:
                    nd = results[0]
                    if nd.id in self._node_map:
                        self._select_node(self._node_map[nd.id])
                        self._frame_node(cam, self._node_map[nd.id])
                    else:
                        self._expand_node(nd)
                        self._expanded = None
                        self._select_node(nd)
                        self._pending_frame_id = nd.id

            # --- Draw ---
            rl.BeginDrawing()
            rl.ClearBackground(_col(*COL_BG))

            rl.BeginMode2D(cam[0])

            # Edges
            sel_edge_ids = set()
            if self._selected:
                sel_edge_ids = {e.src_id for e in self._edges if e.dst_id == self._selected.id} | \
                               {e.dst_id for e in self._edges if e.src_id == self._selected.id}
            for e in self._edges:
                hi = (self._selected and
                      (e.src_id == self._selected.id or e.dst_id == self._selected.id))
                self._draw_edge(cam, e, hi)

            # Nodes
            for n in self._nodes:
                self._draw_node(n)

            rl.EndMode2D()

            # Labels drawn in screen space (after EndMode2D so raylib doesn't
            # double-transform the already-converted screen coordinates).
            if cam.zoom > 0.18:
                for n in self._nodes:
                    self._draw_label(cam, n)

            # Minimap
            self._draw_minimap(cam)

            # Inspection panel
            self._draw_panel()


            # Context menu overlay
            if self._ctx_menu:
                self._draw_ctx_menu(self._ctx_menu)

            # Layout cooling indicator
            temp = self._layout.temperature
            if temp > 1.0:
                prog = max(0.0, min(1.0, 1.0 - temp / 120.0))
                bar_w = int(prog * 120)
                rl.DrawRectangle(12, SCREEN_H - 16, 120, 6, _col(40, 44, 58, 200))
                rl.DrawRectangle(12, SCREEN_H - 16, bar_w, 6, _col(80, 140, 220, 200))
                self._draw_text("settling…", 140, SCREEN_H - 17, 10, COL_TEXT_DIM)

            rl.EndDrawing()

        self._layout.stop()
        rl.CloseWindow()


# ---------------------------------------------------------------------------
# Entry point (also used by tools/graph_explorer.py)
# ---------------------------------------------------------------------------

def resolve_db(arg: str) -> str:
    """Accept a DB path or a corpus name like 'dj2' and return the DB path."""
    p = Path(arg)
    if p.exists():
        return str(p)
    # Try the Determined root DB naming convention
    root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        root / f"C_Users_bartl_dev_{arg}.db",
        root / f"C_Users_bartl_dev_corpora_{arg}.db",
        root / f"{arg}.db",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise FileNotFoundError(f"No DB found for '{arg}'. Pass a full path or a corpus name.")


def launch(db_path: str):
    """Called by tools/graph_explorer.py and the UI server subprocess."""
    explorer = GraphExplorer(db_path)
    explorer.run()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python graph_explorer.py <db_path_or_corpus_name>")
        sys.exit(1)
    launch(resolve_db(sys.argv[1]))
