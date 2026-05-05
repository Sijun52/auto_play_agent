# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync          # install dependencies (first time or after pyproject.toml changes)
uv run apa       # run the agent
```

No test suite or linter is configured. The project uses `hatchling` as the build backend.

## Architecture

Auto Play Agent is an **orchestrator** that drives OpenCode (an AI coding assistant with an HTTP server mode) overnight. The flow per run:

```
run() in agent.py
  └─ checkout_nightly_branch()          # one branch for the whole night
  └─ for each pending task (priority-sorted):
       _make_prompt(task)               # LLM generates a precise implementation prompt
       oc.send_message(session_id, …)   # sends prompt to OpenCode
       for turn in 1..MAX_REVIEW_TURNS:
           oc.wait_until_idle()         # polls until OpenCode goes quiet (20 s stable)
           get_diff()                   # reads git diff HEAD
           _review(task, result, diff)  # LLM returns JSON: complete | needs_work
           if complete → git commit, break
           if needs_work → send follow_up prompt, continue
  └─ push_branch() → create_pr()       # one GitHub PR for all tasks at end
  └─ _suggest_improvements()           # LLM proposes follow-ups
```

### Key design decisions

- **Three LLM roles** (`prompts.py`): `SYSTEM_LEAD` writes implementation prompts, `SYSTEM_REVIEWER` returns structured JSON reviews (status / issues / follow_up / summary), `SYSTEM_ANALYST` finds improvements. All use the same company LLM via `_chat()`.
- **Completion detection** (`opencode.py:wait_until_idle`): polls `GET /session/{id}/message` every `POLL_INTERVAL` seconds; considers done when assistant message count hasn't grown for `STABLE_THRESHOLD` seconds.
- **Task file format** (`task_manager.py`): `tasks.md` uses `### [marker] Title` headers. Status markers: `[ ]` pending, `[~]` in_progress, `[x]` completed, `[!]` failed. Completed/failed tasks are extracted and appended to `tasks_done.md` with timestamp and branch.
- **Crash recovery**: on startup `reset_in_progress()` resets any `[~]` tasks back to `[ ]` so they're retried.
- **Nightly branch**: all tasks commit to `feature/ai-nightly-YYYY-MM-DD` sequentially, eliminating inter-task merge conflicts. One PR is created at the end via GitHub REST API (`GITHUB_TOKEN`).
- **Failed task cleanup**: `git reset --hard HEAD` discards partial changes so the next task starts from a clean working tree.

### Module responsibilities

| Module | Responsibility |
|---|---|
| `agent.py` | `AutoPlayAgent` orchestrator — the only place that coordinates all other modules |
| `opencode.py` | REST client for `opencode serve`; owns the polling/idle-detection loop |
| `task_manager.py` | Reads/writes `tasks.md`; archives to `tasks_done.md` |
| `git.py` | git subprocess wrappers + GitHub REST API PR creation |
| `config.py` | All env vars and tuneable constants (`POLL_INTERVAL`, `STABLE_THRESHOLD`, `SESSION_TIMEOUT`, `MAX_REVIEW_TURNS`) |
| `prompts.py` | Three LLM system prompts as module-level constants |
| `models.py` | `Task` dataclass |

### Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL` | Company private LLM (OpenAI-compatible) |
| `OPENCODE_PORT` | Port of `opencode serve` (default 4096) |
| `PROJECT_DIR` | Absolute path to the target git repo where OpenCode works |
| `TASKS_FILE` | Path to `tasks.md` (default: `./tasks.md`) |
| `BASE_BRANCH` | PR target branch (`main`, `master`, `development`, …) |
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope — required for PR creation |
