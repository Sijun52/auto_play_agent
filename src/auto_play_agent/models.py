import re
from dataclasses import dataclass, field


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
