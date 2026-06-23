# determined.graph.symbol_resolution.py
def resolve_symbol_identity(name: str, alias_map: dict[str, str]) -> str:
    """
    Convert raw AST call names into canonical identity space.
    """

    # direct alias resolution first
    if name in alias_map:
        name = alias_map[name]

    # collapse dotted runtime chains
    return name.split(".")[-1]