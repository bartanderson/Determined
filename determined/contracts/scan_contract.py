# tools/analysis/contracts/scan_contract.py

from .load_contract import load_system_contract


def get_scan_rules():
    contract = load_system_contract()
    return contract["domains"]["ingestion"]["rules"]


def get_dependency_rules():
    contract = load_system_contract()
    return contract["dependency_rules"]["allowed"]["ingestion"]