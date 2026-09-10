import os
import json
import asyncio
import webbrowser
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from .config import Config, config as global_config
from .agent import AgentLoop
from .tools import file_tree, list_dir

app = FastAPI(title="LocalCoder Web UI", version="0.1.0")

# Pending command approvals stored by prompt session ID
pending_approvals: Dict[str, asyncio.Event] = {}
approval_results: Dict[str, bool] = {}


class ConfigUpdateRequest(BaseModel):
    openai_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    model_name: Optional[str] = None
    max_turn_steps: Optional[int] = None
    auto_approve_commands: Optional[bool] = None
    workspace_dir: Optional[str] = None


@app.get("/api/config")
async def get_config():
    return global_config.model_dump()


@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    if req.openai_base_url is not None:
        global_config.openai_base_url = req.openai_base_url
    if req.openai_api_key is not None:
        global_config.openai_api_key = req.openai_api_key
    if req.model_name is not None:
        global_config.model_name = req.model_name
    if req.max_turn_steps is not None:
        global_config.max_turn_steps = req.max_turn_steps
    if req.auto_approve_commands is not None:
        global_config.auto_approve_commands = req.auto_approve_commands
    if req.workspace_dir is not None:
        global_config.workspace_dir = req.workspace_dir
    return {"status": "success", "config": global_config.model_dump()}


@app.get("/api/files")
async def get_files(path: str = "."):
    tree = file_tree(global_config.workspace_dir, path, max_depth=4)
    return {"tree": tree}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def ws_event_handler(event: dict):
        try:
            await websocket.send_text(json.dumps(event))
        except Exception:
            pass

    async def ws_approval_handler(tool_name: str, args: dict) -> bool:
        call_id = f"cmd_{os.urandom(4).hex()}"
        event_data = {
            "type": "approval_required",
            "data": {
                "call_id": call_id,
                "tool_name": tool_name,
                "command": args.get("command", ""),
                "cwd": args.get("cwd", ".")
            }
        }
        await websocket.send_text(json.dumps(event_data))

        evt = asyncio.Event()
        pending_approvals[call_id] = evt
        try:
            await asyncio.wait_for(evt.wait(), timeout=120.0)
            approved = approval_results.pop(call_id, True)
            return approved
        except asyncio.TimeoutError:
            pending_approvals.pop(call_id, None)
            return False

    try:
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)

            msg_type = data.get("type")

            if msg_type == "approval_response":
                call_id = data.get("call_id")
                approved = data.get("approved", True)
                if call_id in pending_approvals:
                    approval_results[call_id] = approved
                    pending_approvals[call_id].set()

            elif msg_type == "start_agent":
                goal = data.get("goal")
                if not goal:
                    continue

                # Optionally update config from payload
                if "base_url" in data and data["base_url"]:
                    global_config.openai_base_url = data["base_url"]
                if "model" in data and data["model"]:
                    global_config.model_name = data["model"]

                agent = AgentLoop(
                    config=global_config,
                    event_callback=ws_event_handler,
                    approval_callback=ws_approval_handler
                )

                # Run agent task asynchronously
                asyncio.create_task(agent.run(goal))

    except WebSocketDisconnect:
        pass


WEB_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LocalCoder - AI Coding Agent</title>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #0b0f19;
      --bg-card: rgba(18, 26, 43, 0.7);
      --bg-card-hover: rgba(26, 38, 63, 0.8);
      --border-color: rgba(255, 255, 255, 0.08);
      --accent-cyan: #38bdf8;
      --accent-green: #4ade80;
      --accent-purple: #c084fc;
      --accent-amber: #fbbf24;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', sans-serif;
      background: var(--bg-dark);
      color: var(--text-main);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(56, 189, 248, 0.06) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(192, 132, 252, 0.06) 0%, transparent 40%);
    }

    header {
      height: 60px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      backdrop-filter: blur(12px);
      background: rgba(11, 15, 25, 0.8);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 1.1rem;
      font-weight: 700;
      letter-spacing: -0.5px;
    }
    .brand-badge {
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
      color: #000;
      font-size: 0.7rem;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: 12px;
      text-transform: uppercase;
    }

    .header-controls {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .status-indicator {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-green);
      box-shadow: 0 0 10px var(--accent-green);
    }

    .btn {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .btn:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
    }
    .btn-primary {
      background: linear-gradient(135deg, #0284c7, #4f46e5);
      border: none;
      font-weight: 600;
    }
    .btn-primary:hover {
      opacity: 0.9;
    }

    main {
      flex: 1;
      display: grid;
      grid-template-columns: 320px 1fr;
      overflow: hidden;
    }

    sidebar {
      border-right: 1px solid var(--border-color);
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 20px;
      background: rgba(15, 23, 42, 0.4);
    }

    .panel-title {
      font-size: 0.8rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--text-muted);
      margin-bottom: 10px;
    }

    .setting-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-bottom: 14px;
    }
    .setting-group label {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .setting-group input, .setting-group select {
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 0.85rem;
      outline: none;
    }
    .setting-group input:focus, .setting-group select:focus {
      border-color: var(--accent-cyan);
    }

    .tree-box {
      flex: 1;
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px;
      font-family: 'Fira Code', monospace;
      font-size: 0.8rem;
      white-space: pre;
      overflow: auto;
      color: var(--text-muted);
    }

    .chat-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
    }

    .feed {
      flex: 1;
      padding: 24px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .msg-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 18px;
      line-height: 1.6;
      backdrop-filter: blur(10px);
      animation: fadeIn 0.3s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .msg-user {
      border-left: 4px solid var(--accent-cyan);
      background: rgba(56, 189, 248, 0.05);
    }
    .msg-assistant {
      border-left: 4px solid var(--accent-purple);
    }

    .tool-card {
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      margin-top: 10px;
      overflow: hidden;
    }
    .tool-header {
      background: rgba(255, 255, 255, 0.03);
      padding: 8px 14px;
      font-size: 0.8rem;
      font-weight: 600;
      font-family: 'Fira Code', monospace;
      color: var(--accent-cyan);
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--border-color);
    }
    .tool-body {
      padding: 12px 14px;
      font-family: 'Fira Code', monospace;
      font-size: 0.8rem;
      white-space: pre-wrap;
      max-height: 250px;
      overflow-y: auto;
      color: #e2e8f0;
    }

    .approval-modal {
      background: rgba(251, 191, 36, 0.1);
      border: 1px solid var(--accent-amber);
      border-radius: 10px;
      padding: 16px;
      margin-top: 12px;
    }
    .approval-actions {
      display: flex;
      gap: 10px;
      margin-top: 12px;
    }

    .input-area {
      padding: 20px 24px;
      border-top: 1px solid var(--border-color);
      background: rgba(11, 15, 25, 0.9);
      display: flex;
      gap: 12px;
    }

    .prompt-input {
      flex: 1;
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 14px 18px;
      border-radius: 10px;
      font-size: 0.95rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s ease;
    }
    .prompt-input:focus {
      border-color: var(--accent-cyan);
    }

  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>🤖 LocalCoder</span>
      <span class="brand-badge">OpenAI Local Loop</span>
    </div>
    <div class="header-controls">
      <div class="status-indicator">
        <span class="dot" id="statusDot"></span>
        <span id="statusText">Connected to WS</span>
      </div>
    </div>
  </header>

  <main>
    <sidebar>
      <div class="panel-title">Model Settings</div>
      
      <div class="setting-group">
        <label>OpenAI Base URL</label>
        <input type="text" id="baseUrlInput" value="http://localhost:11434/v1">
      </div>

      <div class="setting-group">
        <label>Model Name</label>
        <input type="text" id="modelInput" value="qwen2.5-coder:32b">
      </div>

      <div class="setting-group">
        <label>Presets</label>
        <select id="presetSelect">
          <option value="ollama">Ollama (http://localhost:11434/v1)</option>
          <option value="lmstudio">LM Studio (http://localhost:1234/v1)</option>
          <option value="vllm">vLLM (http://localhost:8000/v1)</option>
          <option value="jan">Jan (http://localhost:1337/v1)</option>
        </select>
      </div>

      <div class="setting-group">
        <label>Command Auto-Approve</label>
        <select id="autoApproveSelect">
          <option value="false">Ask before running shell commands</option>
          <option value="true">Auto-approve shell commands</option>
        </select>
      </div>

      <div class="panel-title" style="margin-top: 10px;">Workspace Files</div>
      <div class="tree-box" id="fileTreeBox">Loading directory tree...</div>
    </sidebar>

    <div class="chat-container">
      <div class="feed" id="feed">
        <div class="msg-card msg-assistant">
          <strong>🤖 LocalCoder Assistant Ready</strong>
          <p style="margin-top: 6px; color: var(--text-muted);">Specify a coding task below. I can read, edit, write files and execute bash commands to build your solution!</p>
        </div>
      </div>

      <div class="input-area">
        <input type="text" class="prompt-input" id="promptInput" placeholder="Describe what you want to code or run..." onkeydown="if(event.key==='Enter') sendGoal()">
        <button class="btn btn-primary" onclick="sendGoal()">Run Agent Loop</button>
      </div>
    </div>
  </main>

  <script>
    let ws;
    const feed = document.getElementById('feed');
    const promptInput = document.getElementById('promptInput');
    const baseUrlInput = document.getElementById('baseUrlInput');
    const modelInput = document.getElementById('modelInput');
    const autoApproveSelect = document.getElementById('autoApproveSelect');
    const fileTreeBox = document.getElementById('fileTreeBox');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');

    function connectWS() {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(`${protocol}//${location.host}/ws`);

      ws.onopen = () => {
        statusDot.style.background = '#4ade80';
        statusText.innerText = 'Connected';
        fetchTree();
      };

      ws.onclose = () => {
        statusDot.style.background = '#f87171';
        statusText.innerText = 'Disconnected - Retrying...';
        setTimeout(connectWS, 3000);
      };

      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        handleWsEvent(payload);
      };
    }

    document.getElementById('presetSelect').addEventListener('change', (e) => {
      const val = e.target.value;
      if (val === 'ollama') baseUrlInput.value = 'http://localhost:11434/v1';
      if (val === 'lmstudio') baseUrlInput.value = 'http://localhost:1234/v1';
      if (val === 'vllm') baseUrlInput.value = 'http://localhost:8000/v1';
      if (val === 'jan') baseUrlInput.value = 'http://localhost:1337/v1';
    });

    async function fetchTree() {
      try {
        const res = await fetch('/api/files');
        const data = await res.json();
        fileTreeBox.innerText = data.tree;
      } catch(e) {}
    }

    function sendGoal() {
      const goal = promptInput.value.trim();
      if (!goal) return;

      appendUserMsg(goal);
      promptInput.value = '';

      ws.send(JSON.stringify({
        type: 'start_agent',
        goal: goal,
        base_url: baseUrlInput.value.trim(),
        model: modelInput.value.trim()
      }));
    }

    function appendUserMsg(text) {
      const card = document.createElement('div');
      card.className = 'msg-card msg-user';
      card.innerHTML = `<strong>👤 User Goal:</strong><p style="margin-top:4px;">${escapeHtml(text)}</p>`;
      feed.appendChild(card);
      feed.scrollTop = feed.scrollHeight;
    }

    function handleWsEvent(evt) {
      const type = evt.type;
      const data = evt.data || {};

      if (type === 'assistant_message') {
        const card = document.createElement('div');
        card.className = 'msg-card msg-assistant';
        card.innerHTML = `<strong>🤖 Assistant Thinking:</strong><p style="margin-top:6px; white-space:pre-wrap;">${escapeHtml(data.content)}</p>`;
        feed.appendChild(card);
      } else if (type === 'tool_call_start') {
        const card = document.createElement('div');
        card.className = 'msg-card msg-assistant';
        card.innerHTML = `
          <strong>🛠 Tool Invoked: <span style="color:var(--accent-cyan)">${data.name}</span></strong>
          <div class="tool-card">
            <div class="tool-header">Arguments</div>
            <div class="tool-body">${escapeHtml(JSON.stringify(data.args, null, 2))}</div>
          </div>
        `;
        feed.appendChild(card);
      } else if (type === 'tool_call_completed') {
        const card = document.createElement('div');
        card.className = 'msg-card msg-assistant';
        card.innerHTML = `
          <strong>📋 Tool Output: <span style="color:var(--accent-green)">${data.name}</span></strong>
          <div class="tool-card">
            <div class="tool-body">${escapeHtml(data.result)}</div>
          </div>
        `;
        feed.appendChild(card);
        fetchTree();
      } else if (type === 'approval_required') {
        const card = document.createElement('div');
        card.className = 'approval-modal';
        card.innerHTML = `
          <strong>⚠️ Approval Required for Shell Command</strong>
          <p style="margin-top:4px; font-family:'Fira Code', monospace; color:#fef08a;">${escapeHtml(data.command)}</p>
          <div class="approval-actions">
            <button class="btn btn-primary" onclick="respondApproval('${data.call_id}', true)">Approve & Run</button>
            <button class="btn" onclick="respondApproval('${data.call_id}', false)">Reject</button>
          </div>
        `;
        feed.appendChild(card);
      } else if (type === 'goal_completed') {
        const card = document.createElement('div');
        card.className = 'msg-card msg-assistant';
        card.style.borderColor = 'var(--accent-green)';
        card.innerHTML = `<strong>✅ Goal Completed in ${data.steps} turns!</strong>`;
        feed.appendChild(card);
        fetchTree();
      } else if (type === 'error') {
        const card = document.createElement('div');
        card.className = 'msg-card msg-assistant';
        card.style.borderColor = '#f87171';
        card.innerHTML = `<strong>❌ Error:</strong> <p>${escapeHtml(data.message)}</p>`;
        feed.appendChild(card);
      }

      feed.scrollTop = feed.scrollHeight;
    }

    function respondApproval(call_id, approved) {
      ws.send(JSON.stringify({
        type: 'approval_response',
        call_id: call_id,
        approved: approved
      }));
    }

    function escapeHtml(text) {
      return String(text || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    connectWS();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTMLResponse(content=WEB_UI_HTML)


def start_server(cfg: Config):
    print(f"🚀 Starting LocalCoder Web Server at http://{cfg.server_host}:{cfg.server_port}")
    webbrowser.open(f"http://{cfg.server_host}:{cfg.server_port}")
    uvicorn.run(app, host=cfg.server_host, port=cfg.server_port, log_level="info")
