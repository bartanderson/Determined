"""
lang_quality_probe.py -- per-language call-graph quality report for any corpus.

Usage:
    python tools/lang_quality_probe.py <corpus_root> [--sample N]

Runs LanguageWalker on every supported file in the corpus and reports:
  - File and symbol counts per language
  - Edge count and edge-to-symbol ratio (density)
  - Stub fraction (symbols with no body)
  - Callee uniqueness (distinct callees vs total edges -- low = repetitive noise)
  - Top N callers by out-degree
  - Top N callees by in-degree
  - Random sample of edges for manual spot-check

Languages detected: JS, TS, JSX, TSX, Go, Rust.
Python / other languages are handled by the legacy parse_ast path and are not
covered here.

Exit code 1 if no supported files found.
"""

from __future__ import annotations

import argparse
import collections
import random
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from determined.ingestion.language_walker import LanguageWalker, detect_language

# Extensions this probe covers
_SUPPORTED_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".go", ".rs"}

# Language -> display label
_LANG_LABEL = {
    "javascript": "JS",
    "jsx": "JSX",
    "typescript": "TS",
    "tsx": "TSX",
    "go": "Go",
    "rust": "Rust",
}

# Directories universally skipped
_SKIP_DIRS = {
    "node_modules", ".git", "vendor", "target", "__pycache__",
    "dist", "build", ".cache",
}


def _discover_files(root: Path) -> list[Path]:
    files = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix in _SUPPORTED_EXTENSIONS:
            files.append(p)
    return sorted(files)


def _bucket_label(lang: str | None) -> str:
    return _LANG_LABEL.get(lang or "", "unknown")


def _run_probe(corpus_root: Path, sample_n: int) -> int:
    files = _discover_files(corpus_root)
    if not files:
        print(f"No supported files found under {corpus_root}")
        return 1

    # Per-language accumulators
    file_counts: dict[str, int] = collections.defaultdict(int)
    sym_counts: dict[str, int] = collections.defaultdict(int)
    stub_counts: dict[str, int] = collections.defaultdict(int)
    edge_counts: dict[str, int] = collections.defaultdict(int)
    parse_errors: dict[str, int] = collections.defaultdict(int)

    # For top-N and sample
    all_edges: list[tuple[str, str, str]] = []          # (lang_label, caller, callee)
    callee_freq: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    caller_freq: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    callee_sets: dict[str, set] = collections.defaultdict(set)

    for path in files:
        lang = detect_language(str(path))
        if lang is None:
            continue
        label = _bucket_label(lang)
        file_counts[label] += 1

        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
            walker = LanguageWalker(src, str(path), lang)
            syms = walker.symbols()
            edges = walker.call_edges()
        except Exception as exc:
            parse_errors[label] += 1
            continue

        sym_counts[label] += len(syms)
        stub_counts[label] += sum(1 for s in syms if s.get("is_stub"))
        edge_counts[label] += len(edges)

        for caller_fqdn, callee_name, _etype, _resolved in edges:
            all_edges.append((label, caller_fqdn, callee_name))
            callee_freq[label][callee_name] += 1
            caller_freq[label][caller_fqdn] += 1
            callee_sets[label].add(callee_name)

    if not file_counts:
        print("No files could be parsed.")
        return 1

    # --- Report ---
    print("=" * 70)
    print(f"  Language Quality Probe: {corpus_root}")
    print("=" * 70)

    all_labels = sorted(file_counts.keys())

    # Summary table
    header = f"{'Lang':<8} {'Files':>6} {'Symbols':>8} {'Stubs%':>7} {'Edges':>7} {'Density':>8} {'UniqCallees':>12} {'Errors':>7}"
    print()
    print(header)
    print("-" * len(header))

    for label in all_labels:
        syms = sym_counts[label]
        stubs = stub_counts[label]
        edges = edge_counts[label]
        stub_pct = f"{100*stubs/syms:.0f}%" if syms else "n/a"
        density = f"{edges/syms:.2f}" if syms else "n/a"
        uniq = len(callee_sets[label])
        errors = parse_errors[label]
        print(f"{label:<8} {file_counts[label]:>6} {syms:>8} {stub_pct:>7} {edges:>7} {density:>8} {uniq:>12} {errors:>7}")

    print()
    print("  Density = edges / symbols (healthy range: 1.5-5.0)")
    print("  Stubs%  = symbols with no body (pure declarations)")

    # Per-language top callers / callees
    for label in all_labels:
        if not edge_counts[label]:
            print(f"\n  [{label}] No edges found.")
            continue

        print(f"\n{'─'*70}")
        print(f"  [{label}] Top 10 callers (out-degree)")
        print(f"{'─'*70}")
        for caller, cnt in caller_freq[label].most_common(10):
            print(f"    {cnt:>4}  {caller}")

        print(f"\n  [{label}] Top 10 callees (in-degree -- high = possibly noise)")
        for callee, cnt in callee_freq[label].most_common(10):
            print(f"    {cnt:>4}  {callee}")

    # Edge sample for spot-checking
    if sample_n > 0 and all_edges:
        print(f"\n{'─'*70}")
        print(f"  Random edge sample (n={min(sample_n, len(all_edges))} of {len(all_edges)} total)")
        print(f"{'─'*70}")
        sample = random.sample(all_edges, min(sample_n, len(all_edges)))
        for label, caller, callee in sorted(sample, key=lambda t: t[0]):
            print(f"  [{label}]  {caller}  →  {callee}")

    # Zero-symbol files warning
    for label in all_labels:
        if file_counts[label] > 0 and sym_counts[label] == 0:
            print(f"\n  WARNING [{label}]: {file_counts[label]} files parsed, 0 symbols extracted.")
            print(f"           This usually means the tree-sitter patterns don't match this code style.")

    print()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Language call-graph quality probe")
    parser.add_argument("corpus_root", help="Path to corpus directory")
    parser.add_argument(
        "--sample", type=int, default=20,
        help="Number of random edges to print for manual spot-check (default: 20)"
    )
    args = parser.parse_args()

    root = Path(args.corpus_root)
    if not root.is_dir():
        print(f"Error: {root} is not a directory")
        sys.exit(1)

    sys.exit(_run_probe(root, args.sample))


if __name__ == "__main__":
    main()
