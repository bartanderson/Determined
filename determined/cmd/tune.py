# determined/cmd/tune.py
#
# Probe hardware and write recommended LLM settings.
# Computes ctx-size AND -ngl (GPU layers) for both models running simultaneously.
#
# Usage:
#   python -m determined.cmd.tune           -- show recommendations + setup guide
#   python -m determined.cmd.tune --write   -- write determined.cfg, update bat, update NSSM service

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

# ── Model layer geometry (for -ngl calculations) ──────────────────────────────
# VRAM per layer = model_weights_mb / n_layers  (approximate, Q4_K_M)
_MODEL_PROFILES = {
    "3b":  {"n_layers": 28, "weights_mb": 2_048},   # Llama 3.2 3B Q4 ≈ 2 GB
    "27b": {"n_layers": 36, "weights_mb": 16_384},  # Qwen3.6-27B Q4_K_M ≈ 16 GB
}

# KV-cache bytes per token (F16 KV)
# Formula: 2 * n_layers * n_kv_heads * head_dim * sizeof(float16)
_KV_BYTES_PER_TOKEN = {
    "3b":  57_344,   # 28 layers, 8 KV heads, head_dim=64
    "27b": 147_456,  # 36 layers, 8 KV heads, head_dim=128
}

_SAFETY = 0.80
_CTX_LADDER = [131072, 65536, 32768, 16384, 8192, 4096, 2048]

_DEFAULT_FAST_MODEL   = r"C:\Users\bartl\models\gguf\llama3.2-3b.gguf"
_DEFAULT_QUALITY_MODEL = r"C:\Users\bartl\models\gguf\Qwen3.6-27B-Q4_K_M.gguf"
_DEFAULT_BAT          = r"C:\Users\bartl\models\start-quality-llm.bat"
_NSSM_SERVICE         = "llama-server"


# ── Hardware detection ─────────────────────────────────────────────────────────

_NVIDIA_SMI_CANDIDATES = [
    "nvidia-smi",
    r"C:\Windows\System32\nvidia-smi.exe",
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
]


def _nvidia_smi_query(field: str) -> str | None:
    """Query a single nvidia-smi field; returns the value string or None."""
    for exe in _NVIDIA_SMI_CANDIDATES:
        try:
            out = subprocess.check_output(
                [exe, f"--query-gpu={field}", "--format=csv"],
                stderr=subprocess.DEVNULL, text=True, timeout=10,
            )
            # Output: "field [unit]\nvalue unit\n" — skip header, grab digits
            lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
            for line in reversed(lines):
                m = re.search(r"(\d+)", line)
                if m:
                    return m.group(1)
        except Exception:
            continue
    return None


def _detect_total_vram_mb() -> int | None:
    v = _nvidia_smi_query("memory.total")
    return int(v) if v else None


def _detect_free_vram_mb() -> int | None:
    v = _nvidia_smi_query("memory.free")
    return int(v) if v else None


def _detect_gpu_name() -> str:
    for exe in _NVIDIA_SMI_CANDIDATES:
        try:
            out = subprocess.check_output(
                [exe, "--query-gpu=name", "--format=csv"],
                stderr=subprocess.DEVNULL, text=True, timeout=10,
            )
            lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
            # Last non-empty line is the value (skip header)
            if len(lines) >= 2:
                return lines[-1]
        except Exception:
            continue
    return "unknown"


def _get_nssm_params(service: str) -> tuple[str, str] | None:
    """Return (exe_path, app_params) for an NSSM service, or None."""
    try:
        exe = subprocess.check_output(
            ["nssm", "get", service, "Application"],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
        params = subprocess.check_output(
            ["nssm", "get", service, "AppParameters"],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
        return exe, params
    except Exception:
        return None


# ── Calculation helpers ────────────────────────────────────────────────────────

def _snap_ctx(tokens: int) -> int:
    for snap in _CTX_LADDER:
        if tokens >= snap:
            return snap
    return 2048


def _recommend_ctx(vram_mb: int, kv_per_token: int, model_cap: int = 131072) -> int:
    usable = int(vram_mb * 1024 * 1024 * _SAFETY)
    ctx = usable // kv_per_token
    return min(_snap_ctx(ctx), model_cap)


def _recommend_ngl(available_vram_mb: int, model_key: str) -> int:
    """How many layers of model_key fit in available_vram_mb."""
    p = _MODEL_PROFILES[model_key]
    mb_per_layer = p["weights_mb"] / p["n_layers"]
    layers = int(available_vram_mb * _SAFETY / mb_per_layer)
    return min(layers, p["n_layers"])


# ── Main ───────────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    print("=== Determined LLM Tuner ===\n")

    gpu_name   = _detect_gpu_name()
    total_vram = _detect_total_vram_mb()
    free_vram  = _detect_free_vram_mb()

    quality_model_mb = 0
    qm = Path(args.quality_model)
    if qm.exists():
        quality_model_mb = qm.stat().st_size // (1024 * 1024)

    fast_model_mb = 0
    fm = Path(args.fast_model)
    if fm.exists():
        fast_model_mb = fm.stat().st_size // (1024 * 1024)

    print(f"GPU:          {gpu_name}")
    if total_vram:
        print(f"VRAM total:   {total_vram:,} MiB")
    if free_vram is not None:
        print(f"VRAM free:    {free_vram:,} MiB  (current, reflects loaded models)")
    if quality_model_mb:
        print(f"27B model:    {quality_model_mb:,} MiB")
    if fast_model_mb:
        print(f"3B model:     {fast_model_mb:,} MiB")
    print()

    if total_vram:
        # 27B: takes as many layers as fit; rest spill to CPU
        ngl_27b = _recommend_ngl(total_vram, "27b")
        vram_used_by_27b = int(ngl_27b * (_MODEL_PROFILES["27b"]["weights_mb"] / _MODEL_PROFILES["27b"]["n_layers"]))

        # 3B: gets whatever is left after 27B
        vram_left_for_3b = max(0, total_vram - vram_used_by_27b)
        ngl_3b_with_27b = _recommend_ngl(vram_left_for_3b, "3b")
        ngl_3b_solo = min(_MODEL_PROFILES["3b"]["n_layers"], 99)  # 99 = all layers

        # ctx-size: based on leftover VRAM after both models' layers
        vram_for_kv = max(0, total_vram - vram_used_by_27b - int(
            ngl_3b_with_27b * (_MODEL_PROFILES["3b"]["weights_mb"] / _MODEL_PROFILES["3b"]["n_layers"])
        ))
        fast_ctx   = max(16384, _recommend_ctx(vram_for_kv, _KV_BYTES_PER_TOKEN["3b"]))
        quality_ctx = _recommend_ctx(total_vram - vram_used_by_27b + vram_for_kv,
                                     _KV_BYTES_PER_TOKEN["27b"], model_cap=32768)
        # quality ctx is limited by free VRAM after 27B weights
        quality_ctx = max(2048, _recommend_ctx(
            total_vram - vram_used_by_27b, _KV_BYTES_PER_TOKEN["27b"], model_cap=32768))

        vram_note = f"VRAM total: {total_vram} MiB, GPU: {gpu_name}"
    else:
        print("Could not detect GPU VRAM. Using conservative defaults.")
        ngl_27b = 99
        ngl_3b_with_27b = 0   # all CPU when unknown
        ngl_3b_solo = 99
        fast_ctx = 16384
        quality_ctx = 4096
        vram_note = "VRAM: unknown"

    print("Recommended settings (both models running simultaneously):")
    print(f"  3B  service  (-ngl): {ngl_3b_with_27b:>3}  layers on GPU  "
          f"(solo: {ngl_3b_solo}, with 27B: {ngl_3b_with_27b})")
    print(f"  27B bat file (-ngl): {ngl_27b:>3}  layers on GPU")
    print(f"  fast_ctx   (3B,  port 8080): {fast_ctx:>7,} tokens")
    print(f"  quality_ctx (27B, port 8081): {quality_ctx:>7,} tokens")
    print()

    # Current NSSM service params
    nssm_info = _get_nssm_params(_NSSM_SERVICE)
    if nssm_info:
        print(f"Current NSSM service ({_NSSM_SERVICE}):")
        print(f"  exe:    {nssm_info[0]}")
        print(f"  params: {nssm_info[1]}")
        print()
        new_params = re.sub(r"-ngl\s+\d+", f"-ngl {ngl_3b_with_27b}", nssm_info[1])
        if new_params == nssm_info[1] and f"-ngl {ngl_3b_with_27b}" not in nssm_info[1]:
            new_params = nssm_info[1] + f" -ngl {ngl_3b_with_27b}"
        print(f"Proposed NSSM params: {new_params}")
        print()
    else:
        new_params = None
        print("(NSSM service not found — skipping service update)")
        print()

    cfg_content = f"""\
# determined.cfg — generated by: python -m determined.cmd.tune
# {vram_note}
# Override any value with env vars: LLM_FAST_CTX, LLM_QUALITY_CTX

[llm]
# Context window for the fast-tier server (3B, port 8080).
# When 27B is also loaded this model runs partially on CPU.
fast_ctx = {fast_ctx}

# Context window for the quality-tier server (27B, port 8081).
quality_ctx = {quality_ctx}

[service]
# GPU layers for the 3B NSSM service when running alongside the 27B.
# With 27B loaded: reduced to leave VRAM headroom. Solo: use 99.
ngl_3b_with_27b = {ngl_3b_with_27b}
ngl_3b_solo = {ngl_3b_solo}
ngl_27b = {ngl_27b}
"""

    _print_setup_guide(args, fast_ctx, quality_ctx, ngl_3b_with_27b, ngl_27b)

    if args.write:
        # 1. Write determined.cfg
        cfg_path = Path(args.output)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(cfg_content, encoding="utf-8")
        print(f"Written: {cfg_path}")

        # 2. Update start-quality-llm.bat
        bat = Path(args.bat)
        if bat.exists():
            text = bat.read_text(encoding="utf-8")
            updated = re.sub(r"--ctx-size \d+", f"--ctx-size {quality_ctx}", text)
            updated = re.sub(r"-ngl\s+\d+", f"-ngl {ngl_27b}", updated)
            if updated != text:
                bat.write_text(updated, encoding="utf-8")
                print(f"Updated:  {bat}")
            else:
                print(f"No change: {bat} (already matches)")

        # 3. Update NSSM service
        if nssm_info and new_params and new_params != nssm_info[1]:
            try:
                subprocess.run(
                    ["nssm", "set", _NSSM_SERVICE, "AppParameters", new_params],
                    check=True, timeout=10,
                )
                subprocess.run(
                    ["nssm", "restart", _NSSM_SERVICE],
                    check=True, timeout=30,
                )
                print(f"Updated + restarted NSSM service: {_NSSM_SERVICE}")
                print(f"  params: {new_params}")
            except Exception as e:
                print(f"WARNING: Could not update NSSM service: {e}")
                print(f"  Run manually (as Administrator):")
                print(f"    nssm set {_NSSM_SERVICE} AppParameters \"{new_params}\"")
                print(f"    nssm restart {_NSSM_SERVICE}")
        elif nssm_info and new_params == nssm_info[1]:
            print(f"No change: NSSM service params already match")
    else:
        print("Run with --write to apply all changes:")
        print(f"  python -m determined.cmd.tune --write")
        print()
        print("determined.cfg that would be written:")
        print(cfg_content)


def _print_setup_guide(args, fast_ctx, quality_ctx, ngl_3b, ngl_27b):
    fast_model  = Path(args.fast_model).name
    quality_model = Path(args.quality_model).name
    bat = Path(args.bat)

    print("=" * 60)
    print("SETUP GUIDE")
    print("=" * 60)
    print()
    print("Two LLM tiers run simultaneously:")
    print(f"  Fast  (3B)  — Windows NSSM service, always on, port 8080")
    print(f"  Quality (27B) — manual start via bat file, port 8081")
    print()
    print("1. NSSM service (3B — set once, runs at boot):")
    print(f"   Model: {fast_model}")
    print(f"   Recommended -ngl: {ngl_3b} (when 27B is also loaded)")
    print(f"   To update service (run as Administrator):")
    print(f"     nssm set {_NSSM_SERVICE} AppParameters \"-m {args.fast_model} --port 8080 --host 127.0.0.1 -ngl {ngl_3b}\"")
    print(f"     nssm restart {_NSSM_SERVICE}")
    print()
    print(f"2. Quality server (27B — start when needed):")
    print(f"   Model: {quality_model}")
    print(f"   Bat file: {bat}")
    print(f"   Recommended: --ctx-size {quality_ctx} -ngl {ngl_27b}")
    print(f"   Start: double-click {bat.name} or run it in a terminal")
    print(f"   Stop:  close the window")
    print()
    print("3. Verify both servers:")
    print("   Invoke-RestMethod http://localhost:8080/health")
    print("   Invoke-RestMethod http://localhost:8081/health")
    print()
    print("4. Env var overrides (optional, no restart needed for ctx):")
    print("   $env:LLM_FAST_CTX    = <tokens>   # override fast-tier ctx")
    print("   $env:LLM_QUALITY_CTX = <tokens>   # override quality-tier ctx")
    print()
    print("=" * 60)
    print()


def main() -> None:
    repo_root = Path(__file__).parent.parent.parent
    parser = argparse.ArgumentParser(
        description="Probe hardware and write recommended LLM ctx-size and -ngl settings."
    )
    parser.add_argument("--write", action="store_true",
                        help="Write determined.cfg, update bat file, update NSSM service")
    parser.add_argument("--output", default=str(repo_root / "determined.cfg"),
                        help="Path for determined.cfg (default: repo root)")
    parser.add_argument("--fast-model",    default=_DEFAULT_FAST_MODEL,
                        help="Path to fast-tier (3B) GGUF")
    parser.add_argument("--quality-model", default=_DEFAULT_QUALITY_MODEL,
                        help="Path to quality-tier (27B) GGUF")
    parser.add_argument("--bat", default=_DEFAULT_BAT,
                        help="Path to start-quality-llm.bat")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
