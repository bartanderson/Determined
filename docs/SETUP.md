Setting Up Determined
=====================

Determined runs on Windows. These instructions are written for Windows with
PowerShell. Linux users should be able to follow along with minor path changes,
but Windows is the supported platform.

---

## Prerequisites

- **Python 3.11.9** (recommended). Other 3.x versions should work.
  Download from https://www.python.org/downloads/
- **Git**
  Download from https://git-scm.com/downloads

---

## Clone the repository

```powershell
git clone https://github.com/bartanderson/Determined.git
cd Determined
```

---

## Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Your prompt should now show `(.venv)` at the start.

---

## Install dependencies

```powershell
pip install -e ".[ui,embeddings]"
```

This installs Determined plus the packages needed for the UI (Flask,
Flask-SocketIO) and semantic search (sentence-transformers).

---

## Download a model

Determined uses a local language model for narration, tagging, and stub
generation. It does not call any external API.

**1. Download llama-server**

Get `llama-server.exe` from https://github.com/ggml-org/llama.cpp/releases
and place it anywhere on your machine.

**2. Download a model file**

Download a GGUF model file from HuggingFace. We use and recommend Qwen3-8B
(Q4_K_M quantization). Place it anywhere on your machine.

**3. Tell Determined where they are**

Open `determined/agent/llm_client.py` and update these two lines near the top:

```python
LLM_SERVER_EXE  = r"C:\path\to\llama-server.exe"
LLM_MODEL_PATH  = r"C:\path\to\your-model.gguf"
```

That is the only file you need to change. The UI starts llama-server
automatically when you launch it. You do not need to start it manually
for normal use.

---

## Start the UI

```powershell
.venv\Scripts\python determined\agent\local_agent.py --ui --port 5050
```

Open your browser to `http://localhost:5050`.

---

## You're ready

Continue to [Getting Started](GETTING_STARTED.md) to load the Commonplace
corpus and take the tour.
