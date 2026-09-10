# 🤖 LocalCoder - Local Autonomous Coding Agent Loop

`local_coder` is a terminal coding agent with a customizable HTTPX model adapter
in the root `agent.py`. It defaults to an OpenAI-compatible request format;
you can change the headers, payload, and response extraction for your own API.

It provides autonomous file reading, writing, editing, code searching, directory inspection, and bash command execution in a feedback loop.

---

## ✨ Features

- **Local LLM Endpoint Support**: Works out-of-the-box with any OpenAI API-compatible local server (`http://localhost:11434/v1`, `http://localhost:1234/v1`, `http://localhost:8000/v1`, etc.).
- **Dual Function Calling Engine**: Supports both standard OpenAI tool definitions schema (`tools=[...]`) and fallback JSON/XML parsing for smaller local models.
- **Full Coding Tool Set**:
  - `read_file(path, start_line, end_line)`
  - `write_file(path, content, overwrite)`
  - `edit_file(path, target_content, replacement_content)`
  - `run_command(command, cwd, timeout)`
  - `list_dir(path)`
  - `grep_search(query, search_path, is_regex)`
  - `file_tree(path, max_depth)`
  - `delete_file(path)`
  - `create_directory(path)`
- **Rich Interactive CLI**: Terminal UI featuring step-by-step progress, syntax-highlighted code panels, and interactive shell command approval prompts.
- **Modern Web Dashboard**: Real-time WebSocket streaming web UI with file tree navigation, dark glassmorphism aesthetics, live tool output streams, and endpoint configuration toggles.
- **Safety First**: Interactive confirmation before executing shell commands (configurable auto-approve mode).

---

## 🚀 Quick Start

### 1. Setup Environment
```bash
./scripts/setup.sh
```
*Or manually:*
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure Local LLM Endpoint
Set the defaults in the root `agent.py`, or override them through `.env` and CLI flags:
```env
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=not-needed
MODEL_NAME=qwen2.5-coder:32b
AUTO_APPROVE_COMMANDS=false
```

### 3. Customize your model API

Edit the root **`agent.py`** (the API integration), rather than
`backend/agent.py` (the execution loop):

| Edit point | Purpose |
| --- | --- |
| `DEFAULT_BASE_URL`, `DEFAULT_API_KEY`, `DEFAULT_MODEL` | Default connection and model |
| `build_url()` | Complete inference URL |
| `build_headers()` | Authentication and custom headers |
| `build_payload()` | Request body, model, messages, generation settings |
| `extract_response()` | Extract answer text or native tool calls from your response |

The request uses `httpx.AsyncClient.post(..., headers=..., json=...)`, with a
120-second timeout and non-streaming responses. Adapt `request()` too if your API
needs a different HTTP method or body encoding. Existing environment variables
and CLI flags override file defaults; remove those overrides if you want to use
only the values in `agent.py`.

For a custom response such as `{"result": {"answer": "model text"}}`, use:

```python
def extract_response(self, response):
    return response.json()["result"]["answer"]
```

Return only the answer text, or a message object with `content` and `tool_calls`.
Preserve conversation history and tool results when customizing the payload:
the agent needs those results to continue working after a tool executes.

If your API does not accept native `tools` fields, set `USE_NATIVE_TOOLS = False`.
This also converts tool history to ordinary text messages. It is an explicit
setting; the client does not retry rejected requests with different payloads.
The system prompt instructs the model to request tools using:

```xml
<tool_call>{"name": "read_file", "arguments": {"path": "src/main.py"}}</tool_call>
```

`backend/tool_parser.py` handles native function calls, complete JSON tool
objects/arrays, fenced JSON, and XML tool-call blocks. It validates registered
tool names, required arguments, argument types, and call IDs. Native calls take
precedence over echoed text calls to avoid running the same request twice.
Malformed requests stop the turn with an error; they are not marked completed.
Tool syntax is reserved for execution, so the model must use ordinary prose for
explanations rather than include illustrative tool requests.

The loop executes parsed tools, adds their results to the next model request,
and continues until the model provides an answer without tool calls or reaches
the configured turn limit. Changing models uses the same API and parser:

```bash
./scripts/run.sh --model another-model --no-checkpoint
./scripts/run.sh --model another-model --no-checkpoint -p "Explain this project"
```

---

## 💻 CLI Usage

The terminal is the default interface; no browser is opened. From the folder you
want to work on, launch the installed agent using its runner's absolute path:

```bash
cd /path/to/your/project
/home/mike/Documents/code/local_coder/scripts/run.sh --no-checkpoint
```

The runner uses LocalCoder's virtual environment and preserves your current
folder. The agent receives the workspace path and top-level listing, then searches
and reads relevant files in subfolders as needed. It does not preload every file.
`--workspace /path/to/project` selects another folder; `WORKSPACE_DIR`, if set,
overrides the default current folder. `--no-checkpoint` disables automatic Git commits.

At the `local_coder >` prompt, enter a question or task. Answers, tool activity,
and approval prompts appear directly in the terminal:

```text
local_coder > Explain how this project starts. Read the relevant files.
local_coder > !ls
local_coder > !git status --short
local_coder > /help
local_coder > /exit
```

Commands starting with `!` run immediately because you explicitly requested them;
their output is available as context for your next question. Each command starts
in the workspace, so `!cd` does not persist between commands.

Optional Bash shortcut for the current terminal session:

```bash
alias localcoder='/home/mike/Documents/code/local_coder/scripts/run.sh --no-checkpoint'
```

You can then run `localcoder` from any project folder. The local model server must
be running to answer questions; use `--url` and `--model` to select it. The `!`
shell commands work without a model server.

Launch the interactive REPL:
```bash
python3 main.py
```

Pass custom endpoint or model options:
```bash
python3 main.py --url http://localhost:1234/v1 --model deepseek-coder
```

Execute a single prompt directly:
```bash
python3 main.py -p "Create a python script that fetches top stories from HackerNews API and formats them as markdown."
```

Auto-approve shell commands:
```bash
python3 main.py -y
```

---

## 🌐 Web UI Usage

Launch the web dashboard:
```bash
python3 main.py --web
```
Open `http://localhost:8000` in your browser.

Features in Web UI:
- Switch between Ollama, LM Studio, vLLM, or Jan presets dynamically.
- Monitor model thinking and tool execution step-by-step.
- Approve or reject pending terminal command executions in real-time.
- View live workspace directory tree.

---

## 🧪 Running Tests

Run the test suite:
```bash
./scripts/test.sh
```

---

## 📂 Project Architecture

```
local_coder/
├── agent.py             # Customize LLM defaults, HTTP request, response extraction
├── backend/
│   ├── agent.py         # Autonomous execution loop & event callbacks
│   ├── config.py        # Environment & runtime configuration
│   ├── llm_client.py    # Shared adapter invocation and HTTP error handling
│   ├── tool_parser.py   # Shared tool-call parsing and argument validation
│   ├── server.py        # FastAPI server & WebSockets dashboard UI
│   └── tools/           # File, code, and terminal execution tools
├── scripts/
│   ├── setup.sh         # Virtual environment & dependency installer
│   ├── run.sh           # Main runner script
│   └── test.sh          # Test runner script
├── tests/               # Pytest suite
├── .env.example         # Template environment variables
├── main.py              # CLI launcher
├── requirements.txt     # Python dependencies
└── README.md
```
