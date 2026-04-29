import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Task:
    title: str
    description: str
    details: str
    priority: str
    status: str      # pending | in_progress | completed | failed
    line_index: int
    branch_slug: str = field(init=False)

    def __post_init__(self):
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        self.branch_slug = slug[:40]

    @property
    def branch_name(self) -> str:
        return f"feature/ai-{self.branch_slug}-{datetime.now().strftime('%Y-%m-%d')}"
