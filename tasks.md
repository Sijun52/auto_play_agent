# Auto Play Agent — Task Queue

퇴근 전 아래 Tasks 섹션에 작업을 추가하고 Agent를 시작하세요.

**Status**
- `[ ]` 대기 (pending) — 사용자가 작성
- `[~]` 진행중 (in_progress) — Agent가 자동 업데이트
- `[x]` 완료 (completed) — Agent가 자동 업데이트, Branch 정보 추가됨
- `[!]` 실패 (failed) — 로그 확인 필요

**Priority**: `high` | `medium` | `low`

---

## Tasks

### [ ] 예시: 로그인 API 입력값 검증 추가
- **Priority**: high
- **Description**: 로그인 엔드포인트에 이메일 형식 검증과 비밀번호 길이 제한 추가
- **Details**: 이메일은 RFC 5322 형식, 비밀번호는 최소 8자 이상. 실패 시 명확한 에러 메시지 반환. 단위 테스트도 작성.

### [ ] 예시: 데이터베이스 커넥션 풀링 도입
- **Priority**: medium
- **Description**: 현재 요청마다 새 DB 커넥션을 생성하는 구조를 커넥션 풀로 전환
- **Details**: min=5, max=20 커넥션. 헬스체크 포함. 타임아웃 설정 추가.
