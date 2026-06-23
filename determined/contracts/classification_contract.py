# tools/analysis/contracts/classification_contract.py

import json
from pathlib import Path


_CONTRACT_PATH = Path(__file__).with_name("classification_contract_v1.json")


class ClassificationContract:
    def __init__(self, raw: dict):
        self.raw = raw
        self.routes = raw["routes"]
        self.rules = raw["rules"]


def load_classification_contract() -> ClassificationContract:
    with _CONTRACT_PATH.open("r", encoding="utf-8") as f:
        return ClassificationContract(json.load(f))