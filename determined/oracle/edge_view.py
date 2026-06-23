# tools/analysis/oracle/edge_view.py

def classify_edge_roles(edge):
    return {
        "caller": edge.caller,
        "callee": edge.callee,
        "is_dependency": True,
        "direction": "caller→callee"
    }