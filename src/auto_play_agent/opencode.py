import time

import requests

from .config import OPENCODE_URL, POLL_INTERVAL, STABLE_THRESHOLD, SESSION_TIMEOUT


class TokenLimitError(Exception):
    """Raised when OpenCode returns 400 with a token/context limit detail."""


class OpenCodeClient:
    """
    REST client for `opencode serve --port 4096`.
    API spec: http://localhost:4096/doc
    """

    def __init__(self, base_url: str = OPENCODE_URL):
        self.base = base_url.rstrip("/")

    def health(self) -> bool:
        try:
            return requests.get(f"{self.base}/health", timeout=3).ok
        except requests.exceptions.ConnectionError:
            return False

    def create_session(self) -> str:
        r = requests.post(f"{self.base}/session", json={}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("id") or data.get("session_id") or list(data.values())[0]

    def send_message(self, session_id: str, content: str) -> None:
        r = requests.post(
            f"{self.base}/session/{session_id}/message",
            json={"role": "user", "content": content},
            timeout=30,
        )
        if r.status_code == 400 and "token limit" in r.text.lower():
            raise TokenLimitError(r.text)
        r.raise_for_status()

    def get_messages(self, session_id: str) -> list[dict]:
        r = requests.get(f"{self.base}/session/{session_id}/message", timeout=10)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("messages", [])

    def delete_session(self, session_id: str) -> None:
        try:
            requests.delete(f"{self.base}/session/{session_id}", timeout=5)
        except Exception:
            pass

    def wait_until_idle(self, session_id: str) -> str:
        """Poll until assistant response stabilizes (no new messages for STABLE_THRESHOLD sec)."""
        deadline = time.time() + SESSION_TIMEOUT
        last_count = 0
        stable_since: float = time.time()  # track from start so 0-message stalls are caught

        while time.time() < deadline:
            msgs = self.get_messages(session_id)
            assistant_msgs = [m for m in msgs if m.get("role") == "assistant"]
            count = len(assistant_msgs)

            if count > last_count:
                last_count = count
                stable_since = time.time()
            elif time.time() - stable_since >= STABLE_THRESHOLD:
                if assistant_msgs:
                    content = assistant_msgs[-1].get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            p.get("text", "") for p in content if isinstance(p, dict)
                        )
                    return content
                raise TimeoutError(
                    f"Session {session_id} produced no response after {STABLE_THRESHOLD}s"
                )

            time.sleep(POLL_INTERVAL)

        raise TimeoutError(f"Session {session_id} timed out after {SESSION_TIMEOUT}s")
