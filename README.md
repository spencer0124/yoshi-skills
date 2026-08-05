# explain-diff (나만의 코드 변경 설명 스킬)

코드 변경(diff / branch / commit / PR)을 받아서, **배경 → 용어집 → 직관 → 코드 워크스루 → 퀴즈** 구조의
자체 완결형 인터랙티브 HTML 문서로 설명해 주는 Claude Code 스킬입니다.
Geoffrey Litt의 explain-diff를 바탕으로 커뮤니티 피드백 4가지를 반영했습니다.

- 퀴즈 정답 위치 랜덤화 (정답이 항상 길거나 특정 위치에 몰리는 문제 해결)
- Glossary(용어집) 섹션 추가
- Prompt injection 방어 (diff 내용은 '실행 지시'가 아니라 '수동 데이터'로만 취급)
- 저장 전 자체 검증 체크리스트

## 설치 (개인 스킬 — 모든 프로젝트에서 사용)

터미널에서:

```bash
mkdir -p ~/.claude/skills/explain-diff
cp SKILL.md ~/.claude/skills/explain-diff/SKILL.md
```

Claude Code는 스킬 디렉터리 변경을 실시간 감지하므로 재시작 없이 바로 잡힙니다.
(세션 시작 후 새로 만든 최상위 skills 디렉터리라면 한 번만 재시작하세요.)

특정 프로젝트에서만 쓰려면 `~/.claude/` 대신 그 프로젝트의 `.claude/skills/explain-diff/`에 넣으세요.

## 사용법

```
/explain-diff <대상>
```

`<대상>` 예시:

- `/explain-diff working tree` — 아직 커밋 안 한 현재 변경
- `/explain-diff my-feature-branch` — 브랜치를 base와 비교
- `/explain-diff abc123..def456` — 커밋 범위
- `/explain-diff PR 42` — PR (gh CLI 필요)
- `/explain-diff src/auth.ts src/session.ts` — 특정 파일

또는 그냥 자연어로 "이 브랜치 변경 좀 설명해줘"처럼 말하면 Claude가 자동으로 스킬을 불러옵니다.

결과 HTML은 저장소 밖 `/tmp/YYYY-MM-DD-explanation-<slug>.html`에 날짜 접두사로 저장됩니다.
브라우저로 열면 됩니다.

## 커스터마이즈 팁

- 설명 언어를 한국어로 바꾸려면 SKILL.md 본문의 "Write in **English**"를 "한국어로 작성"으로 수정하세요.
- Notion 페이지로 뽑고 싶으면 마지막 "Final handoff" 부분을 Notion MCP 사용으로 바꾸면 됩니다.
- 보일러플레이트(CSS/JS)를 매번 새로 생성하기 싫으면 `scripts/render.py`에 렌더러를 두고
  SKILL.md에서 JSON 콘텐츠 스펙만 넘기도록 바꾸는 방식도 있습니다(커뮤니티 fork 참고).
