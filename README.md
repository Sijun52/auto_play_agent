# Auto Play Agent

퇴근 후 사내 Private LLM + OpenCode가 야간에 자동으로 개발을 진행하는 자율 코딩 에이전트.

```
사용자 퇴근
    ↓
Auto Play Agent (Orchestrator LLM)
    ↓  구현 프롬프트 생성
OpenCode (Worker)
    ↓  코드 작업 완료
Auto Play Agent
    ↓  결과 리뷰 → 부족하면 추가 지시 (최대 4턴)
    ↓  완료 → git commit → tasks_done.md 이관
    ↓  모든 태스크 완료 후 미발견 개선점 제안
사용자 출근 후 PR 리뷰
```

---

## 구조

```
auto_play_agent/
├── pyproject.toml               # uv 프로젝트 설정 + 의존성
├── tasks.md                     # 오늘 밤 할 일 (사용자 작성)
├── tasks_done.md                # 완료/실패 이력 (자동 생성)
├── opencode.json                # OpenCode 사내 LLM 설정 → 프로젝트 루트에 복사
├── .env.example                 # 환경변수 템플릿 → .env로 복사
├── README.md
└── src/
    └── auto_play_agent/
        ├── __main__.py          # 진입점 (uv run apa)
        ├── config.py            # 환경변수 / 상수
        ├── models.py            # Task 데이터클래스
        ├── task_manager.py      # tasks.md 읽기/쓰기/이관
        ├── opencode.py          # OpenCode HTTP 클라이언트
        ├── git.py               # git 헬퍼
        ├── prompts.py           # LLM 시스템 프롬프트
        └── agent.py             # AutoPlayAgent 오케스트레이터
```

---

## 세팅

### 1. 환경변수

```bash
cp .env.example .env
```

`.env` 수정:

```env
OPENAI_BASE_URL=http://your-company-llm-server/v1
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4
OPENCODE_PORT=4096
PROJECT_DIR=C:/path/to/your/project
TASKS_FILE=C:/workspace/auto_play_agent/tasks.md
BASE_BRANCH=main
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

`GITHUB_TOKEN`: GitHub → Settings → Developer settings → Personal access tokens → `repo` 권한으로 발급.  
미설정 시 코드 커밋까지는 정상 동작하고 PR 생성만 건너뜁니다.

### 2. OpenCode 사내 LLM 연결

`opencode.json`을 작업 대상 프로젝트 루트에 복사하고 수정:

```json
{
  "provider": {
    "company-llm": {
      "name": "Company Private LLM",
      "apiKey": "your-api-key",
      "options": {
        "baseURL": "http://your-company-llm-server/v1"
      }
    }
  },
  "model": "company-llm/gpt-4"
}
```

> OpenCode REST API 경로는 서버 기동 후 `http://localhost:4096/doc` 에서 확인.  
> 경로가 다를 경우 `auto_play_agent.py`의 `OpenCodeClient` 클래스 URL만 수정.

---

## 사용법

### 퇴근 전

**1. `tasks.md`에 오늘 밤 할 작업 작성**

```markdown
### [ ] 로그인 API 입력값 검증 추가
- **Priority**: high
- **Description**: 로그인 엔드포인트에 이메일 형식 검증과 비밀번호 길이 제한 추가
- **Details**: RFC 5322 이메일 형식, 비밀번호 최소 8자. 단위 테스트 포함.

### [ ] 데이터베이스 커넥션 풀링 도입
- **Priority**: medium
- **Description**: 요청마다 새 DB 커넥션 생성하는 구조를 풀링으로 전환
- **Details**: min=5, max=20. 헬스체크, 타임아웃 설정 포함.
```

**Priority**: `high` > `medium` > `low` 순으로 실행됨.

**2. OpenCode 서버 기동** (작업 대상 프로젝트 디렉토리에서)

```bash
opencode serve --port 4096
```

**3. Agent 시작**

```bash
uv sync       # 최초 1회: 의존성 설치
uv run apa    # Agent 실행
```

### 출근 후

- `tasks_done.md` — 완료된 작업 확인
- 자동 생성된 PR (`feature/ai-nightly-YYYY-MM-DD`) 리뷰 후 머지

---

## tasks.md 상태 마커

| 마커 | 상태 | 설명 |
|------|------|------|
| `[ ]` | pending | 대기 중 — 사용자가 작성 |
| `[~]` | in_progress | 진행 중 — Agent가 자동 업데이트 |
| `[x]` | completed | 완료 — `tasks_done.md`로 이관 |
| `[!]` | failed | 실패 — `tasks_done.md`로 이관, 로그 확인 필요 |

---

## 브랜치 규칙

하루 단위로 브랜치 하나를 생성하고 모든 태스크를 순서대로 커밋합니다.

```
feature/ai-nightly-YYYY-MM-DD
```

예시: `feature/ai-nightly-2026-04-29`

같은 날 재실행 시 자동으로 `-2`, `-3` suffix가 붙습니다.  
PR은 모든 태스크 완료 후 이 브랜치에서 `BASE_BRANCH`로 1개 생성됩니다.

---

## 주요 설정값 (`auto_play_agent.py` 상단)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `POLL_INTERVAL` | 5초 | OpenCode 상태 확인 주기 |
| `STABLE_THRESHOLD` | 20초 | 응답 안정화 판단 시간 |
| `SESSION_TIMEOUT` | 1800초 | 태스크당 최대 실행 시간 (30분) |
| `MAX_REVIEW_TURNS` | 4 | Orchestrator ↔ OpenCode 최대 반복 횟수 |
| `BASE_BRANCH` | `main` | PR 대상 베이스 브랜치 (`.env`로 설정) |
| `GITHUB_TOKEN` | — | GitHub PAT, `repo` 권한 필요. PR 생성에 사용 |
