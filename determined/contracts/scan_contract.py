# tools/analysis/contracts/scan_contract.py

from .load_contract import load_system_contract


def get_scan_rules():
    """Return the ingestion stage invariants from the system contract."""
    contract = load_system_contract()
    return contract["modules"]["ingestion"]["invariants"]


def get_dependency_rules():
    """Return the ordered pipeline stages (implicit dependency chain)."""
    contract = load_system_contract()
    return contract["modules"]["pipeline"]["stages"]