import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
from agent import DEFAULT_BASE_URL, DEFAULT_API_KEY, DEFAULT_MODEL

# Load .env if present
load_dotenv()


class Config(BaseModel):
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", DEFAULT_API_KEY)
    model_name: str = os.getenv("MODEL_NAME", DEFAULT_MODEL)
    model_family: str = os.getenv("MODEL_FAMILY", "generic")
    max_turn_steps: int = int(os.getenv("MAX_TURN_STEPS", "30"))
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "16000"))
    auto_approve_commands: bool = os.getenv("AUTO_APPROVE_COMMANDS", "false").lower() in ("true", "1", "yes")
    auto_checkpoint: bool = os.getenv("AUTO_CHECKPOINT", "true").lower() in ("true", "1", "yes")
    workspace_dir: str = os.getenv("WORKSPACE_DIR", ".")
    server_host: str = os.getenv("SERVER_HOST", "127.0.0.1")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))

    def get_abs_workspace(self) -> Path:
        return Path(self.workspace_dir).resolve()


config = Config()
