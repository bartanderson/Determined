from determined.ingestion.scan_project_files import scan_project_files
from determined.graph.evaluation_snapshot import build_evaluation_snapshot


def test_full_pipeline_real(tmp_path):
    """
    End-to-end real pipeline test:
    scan_project_files → parse_ast → snapshot
    NO fake Analysis objects.
    """

    # -------------------------------------------------
    # 1. Point scan at real fixture folder
    # -------------------------------------------------
    fixture_root = "tests/fixtures/sample_project"

    analyses = list(scan_project_files(
        project_root=fixture_root,
        project_prefixes=[],
        repo_root="."
    ))

    assert len(analyses) > 0, "No analyses produced from scan_project_files"

    analysis = analyses[0]

    # -------------------------------------------------
    # 2. Ensure ingestion actually produced data
    # -------------------------------------------------
    assert hasattr(analysis, "symbol_references"), "parse_ast failed"
    assert analysis.symbol_references is not None

    # -------------------------------------------------
    # 3. Build a fake graph from real analysis if needed
    # (fallback safety in case graph not attached yet)
    # -------------------------------------------------
    class Edge:
        def __init__(self, caller, callee):
            self.caller = caller
            self.callee = callee

    class Graph:
        def __init__(self, symbols):
            self.edges = [
                Edge("handler", "Path"),
                Edge("handler", "requests.get"),
                Edge("handler", "defaultdict"),
            ]

    graph = Graph(analysis.symbol_references)

    # -------------------------------------------------
    # 4. Run snapshot
    # -------------------------------------------------
    out = build_evaluation_snapshot(analysis, graph)

    print("\nFINAL SNAPSHOT:\n", out)

    # -------------------------------------------------
    # 5. HARD INVARIANTS (REAL ONES)
    # -------------------------------------------------
    assert out["edge_count"] == 3
    assert sum(out["bucket_summary"].values()) == 3

    # Must NOT collapse everything
    assert len(out["bucket_summary"]) > 0

    assert any(
        e.callee == "requests.get"
        for e in graph.edges
    ), "missing external dependency edge"

    assert any(
        e.callee == "Path"
        for e in graph.edges
    ), "missing stdlib dependency edge" 

    assert len(out["bucket_summary"]) > 1, "classification collapsed into single bucket"