from pathlib import Path
import json


_CONTRACT_PATH = (
    Path(__file__).resolve().parent
    / "tool_system_contract.json"
)


class ContractLoadError(Exception):
    pass


def load_system_contract():
    try:
        with _CONTRACT_PATH.open(
            "r",
            encoding="utf-8",
        ) as f:
            return json.load(f)

    except Exception as e:
        raise ContractLoadError(
            f"Failed to load contract: {e}"
        ) from e