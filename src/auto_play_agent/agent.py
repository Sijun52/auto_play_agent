import json
import re
import sys
import time
from datetime import datetime

from openai import OpenAI

from .config import (
    MAX_REVIEW_TURNS,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    OPENCODE_PORT,
    PRIORITY_ORDER,
    PROJECT_DIR,
)
from .git import checkout_nightly_branch, create_pr, get_diff, git, has_staged_changes, push_branch
from .models import Task
from .opencode import OpenCodeClient
from .prompts import SYSTEM_ANALYST, SYSTEM_LEAD, SYSTEM_REVIEWER
from .task_manager import TaskManager


class AutoPlayAgent:
    def __init__(self):
        self.llm = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
        self.oc = OpenCodeClient()
        self.tm = TaskManager()

    def _chat(self, system: str, user: str) -> str:
        for attempt in range(3):
            try:
                resp = self.llm.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return resp.choices[0].message.content.strip()
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    def _make_prompt(self, task: Task) -> str:
        return self._chat(
            SYSTEM_LEAD,
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Details: {task.details}\n\n"
            "Write a detailed implementation prompt for OpenCode. "
            "Include exact requirements, acceptance criteria, test expectations, and edge cases.",
        )

    def _review(self, task: Task, result: str, turn: int, diff: str = "") -> dict:
        diff_section = f"\n\nGit diff (actual changes so far):\n{diff}" if diff else ""
        raw = self._chat(
            SYSTEM_REVIEWER,
            f"Task: {task.title}\n"
            f"Description: {task.description}\n\n"
            f"OpenCode output (turn {turn}/{MAX_REVIEW_TURNS}):\n{result}"
            f"{diff_section}\n\n"
            'Return JSON: {"status":"complete"|"needs_work",'
            '"issues":["..."],'
            '"follow_up":"next prompt if needs_work, null if complete",'
            '"summary":"one-line summary"}',
        )
        raw = re.sub(r"^```json?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"status": "complete", "summary": raw, "follow_up": None, "issues": []}

    def _suggest_improvements(self, completed: list[Task]) -> list[str]:
        if not completed:
            return []
        task_list = "\n".join(f"- {t.title}: {t.description}" for t in completed)
        raw = self._chat(
            SYSTEM_ANALYST,
            f"Tasks completed tonight:\n{task_list}\n\n"
            "List 2-3 follow-up improvements not in the original tasks. "
            "Be specific. Format as a numbered list.",
        )
        return [line.strip() for line in raw.split("\n") if line.strip()]

    def _run_task(self, task: Task, nightly_branch: str) -> bool:
        print(f"\n{'━'*64}")
        print(f"  Task    : {task.title}")
        print(f"  Priority: {task.priority}")
        print(f"{'━'*64}")

        try:
            self.tm.set_status(task, "in_progress")

            session_id = self.oc.create_session()
            print(f"  [OpenCode] Session: {session_id}")

            prompt = self._make_prompt(task)
            print("  [Agent]    Sending prompt to OpenCode…")
            self.oc.send_message(session_id, prompt)

            for turn in range(1, MAX_REVIEW_TURNS + 1):
                print(f"  [OpenCode] Working… (turn {turn}/{MAX_REVIEW_TURNS})")
                result = self.oc.wait_until_idle(session_id)

                diff = get_diff()
                review = self._review(task, result, turn, diff)
                status = review.get("status", "complete")
                summary = review.get("summary", "")
                print(f"  [Agent]    Review: {status} — {summary}")

                if status == "complete" or turn == MAX_REVIEW_TURNS:
                    git("add", "-A")
                    if has_staged_changes():
                        git("commit", "-m", f"feat: {task.title}")
                        print(f"  [git]      Committed")
                    else:
                        print("  [git]      No file changes to commit")
                    self.tm.set_status(task, "completed", nightly_branch)
                    self.oc.delete_session(session_id)
                    return True

                follow_up = review.get("follow_up")
                if follow_up:
                    issues = review.get("issues", [])
                    print(f"  [Agent]    Follow-up: {', '.join(str(i) for i in issues[:2])}")
                    self.oc.send_message(session_id, follow_up)

        except Exception as exc:
            print(f"  [ERROR]    {exc}")
            self.tm.set_status(task, "failed", nightly_branch)
            try:
                git("reset", "--hard", "HEAD")  # discard partial changes, stay on nightly branch
            except Exception:
                pass
            return False

    def run(self) -> None:
        print("\n" + "═" * 64)
        print("  Auto Play Agent")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  LLM  : {OPENAI_BASE_URL}  model={OPENAI_MODEL}")
        print(f"  Repo : {PROJECT_DIR.resolve()}")
        print("═" * 64)

        print("\n[1/4] Connecting to OpenCode server…")
        for attempt in range(24):
            if self.oc.health():
                print("      Connected.")
                break
            if attempt == 0:
                print(f"      Waiting… (run: opencode serve --port {OPENCODE_PORT})")
            time.sleep(5)
        else:
            print("      ERROR: OpenCode unreachable after 2 minutes. Aborting.")
            sys.exit(1)

        print("\n[2/4] Loading tasks…")
        reset_count = self.tm.reset_in_progress()
        if reset_count:
            print(f"      Reset {reset_count} in_progress task(s) → pending (crash recovery)")
        all_tasks = self.tm.load()
        pending = sorted(
            [t for t in all_tasks if t.status == "pending"],
            key=lambda t: PRIORITY_ORDER.get(t.priority, 1),
        )
        print(f"      {len(pending)} pending task(s)")
        for t in pending:
            print(f"      [{t.priority:6}] {t.title}")

        if not pending:
            print("\n      Nothing to do. Exiting.")
            return

        print("\n[3/4] Executing tasks…")
        nightly_branch = checkout_nightly_branch()
        print(f"      Branch: {nightly_branch}")

        completed: list[Task] = []
        for task in pending:
            if self._run_task(task, nightly_branch):
                completed.append(task)

        print("\n[4/4] Wrapping up…")
        if completed:
            task_lines = "\n".join(
                f"- **{t.title}**: {t.description}" for t in completed
            )
            pr_body = (
                f"## Tasks completed tonight ({len(completed)}/{len(pending)})\n\n"
                f"{task_lines}\n\n"
                "🤖 Auto-generated by Auto Play Agent"
            )
            if push_branch(nightly_branch):
                try:
                    pr_url = create_pr(
                        f"feat: nightly auto-dev ({datetime.now().strftime('%Y-%m-%d')})",
                        pr_body,
                        nightly_branch,
                    )
                    if pr_url:
                        print(f"      PR created: {pr_url}")
                    else:
                        print("      PR skipped (GITHUB_TOKEN not set or not a GitHub repo)")
                except RuntimeError as pr_err:
                    print(f"      PR creation failed: {pr_err}")
            else:
                print("      Push failed — PR creation skipped")

        suggestions = self._suggest_improvements(completed)
        if suggestions:
            print("\n  Suggested for next session:")
            for s in suggestions:
                if s:
                    print(f"      {s}")

        print(f"\n{'═'*64}")
        print(f"  Completed {len(completed)}/{len(pending)} tasks.")
        print(f"  Branch : {nightly_branch}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("═" * 64 + "\n")
