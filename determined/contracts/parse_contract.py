# tools/analysis/contracts/parse_contract.py

from .load_contract import load_system_contract


def get_parse_domain_contract():
    contract = load_system_contract()
    return contract["domains"]["ingestion"]