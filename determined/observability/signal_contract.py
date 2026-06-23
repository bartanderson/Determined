# tools\analysis\observability\signal_contract.py

VALID_CLASSES = {
    "structure",
    "propagation",
    "invariant",
}


def validate_signal(signal) -> bool:
    return signal.signal_class in VALID_CLASSES


FAILURE_MAP = {
    "structure": {
        "edge_break",
        "identity_shift",
    },
    "propagation": {
        "fault_amplification",
        "downstream_drift",
    },
    "invariant": {
        "count_mismatch",
        "mutation_error",
    },
}


def required_for_failure_detection(signal) -> bool:
    return signal.signal_class in FAILURE_MAP


def prune_signals(signals):
    return [
        s
        for s in signals
        if validate_signal(s)
        and required_for_failure_detection(s)
    ]
