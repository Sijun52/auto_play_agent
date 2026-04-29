import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_BASE_URL  = os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "company-key")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4")
OPENCODE_PORT    = int(os.getenv("OPENCODE_PORT", "4096"))
OPENCODE_URL     = f"http://localhost:{OPENCODE_PORT}"
TASKS_FILE       = Path(os.getenv("TASKS_FILE", str(Path.cwd() / "tasks.md")))
PROJECT_DIR      = Path(os.getenv("PROJECT_DIR", "."))
BASE_BRANCH      = os.getenv("BASE_BRANCH", "main")
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")

POLL_INTERVAL    = 5     # seconds between OpenCode status checks
STABLE_THRESHOLD = 20    # seconds of no new messages = done
SESSION_TIMEOUT  = 1800  # 30 min max per task
MAX_REVIEW_TURNS = 4     # max orchestrator↔OpenCode cycles per task

PRIORITY_ORDER   = {"high": 0, "medium": 1, "low": 2}
