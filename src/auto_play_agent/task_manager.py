import re
from datetime import datetime
from pathlib import Path

from .config import TASKS_FILE
from .models import Task

STATUS_CHAR = {"pending": " ", "in_progress": "~", "completed": "x", "failed": "!"}
CHAR_STATUS = {v: k for k, v in STATUS_CHAR.items()}


class TaskManager:
    def __init__(self, path: Path = TASKS_FILE):
        self.path = path

    def reset_in_progress(self) -> int:
        """Reset [~] tasks back to [ ] at startup (crash recovery). Returns count."""
        lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
        count = sum(1 for l in lines if re.match(r"^### \[~\]", l))
        if count:
            lines = [re.sub(r"^(### \[)~(\] )", r"\g<1> \2", l) for l in lines]
            self.path.write_text("".join(lines), encoding="utf-8")
        return count

    def load(self) -> list[Task]:
        lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)
        return self._parse(lines)

    def _parse(self, lines: list[str]) -> list[Task]:
        tasks: list[Task] = []
        i = 0
        while i < len(lines):
            m = re.match(r"^### \[([x ~!])\] (.+)$", lines[i].rstrip())
            if m:
                status = CHAR_STATUS.get(m.group(1), "pending")
                title = m.group(2).strip()
                desc = details = priority = ""
                j = i + 1
                while j < len(lines) and not re.match(r"^### \[", lines[j]):
                    s = lines[j].strip()
                    if s.startswith("- **Description**:"):
                        desc = s.split(":", 1)[1].strip()
                    elif s.startswith("- **Details**:"):
                        details = s.split(":", 1)[1].strip()
                    elif s.startswith("- **Priority**:"):
                        priority = s.split(":", 1)[1].strip().lower()
                    j += 1
                tasks.append(Task(title, desc, details, priority or "medium", status, i))
            i += 1
        return tasks

    def set_status(self, task: Task, status: str, branch: str = "") -> None:
        lines = self.path.read_text(encoding="utf-8").splitlines(keepends=True)

        if status == "in_progress":
            lines[task.line_index] = re.sub(
                r"^(### \[)[x ~!](\] .+\n?)$", r"\g<1>~\2", lines[task.line_index]
            )
            self.path.write_text("".join(lines), encoding="utf-8")
            return

        # completed / failed → extract block, archive, remove from tasks.md
        end = task.line_index + 1
        while end < len(lines) and not re.match(r"^### \[", lines[end]):
            end += 1

        block = list(lines[task.line_index:end])
        char = STATUS_CHAR[status]
        block[0] = re.sub(r"^(### \[)[x ~!](\] .+\n?)$", rf"\g<1>{char}\2", block[0])

        meta = [f"- **Completed**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
        if branch:
            meta.append(f"- **Branch**: `{branch}`\n")
        block[1:1] = meta

        self._archive(block)

        remaining = lines[: task.line_index] + lines[end:]
        self.path.write_text("".join(remaining), encoding="utf-8")

    def _archive(self, block: list[str]) -> None:
        done_path = self.path.parent / "tasks_done.md"
        if not done_path.exists():
            done_path.write_text("# Auto Play Agent — Completed Tasks\n\n", encoding="utf-8")
        with done_path.open("a", encoding="utf-8") as f:
            f.write("\n")
            f.writelines(block)
