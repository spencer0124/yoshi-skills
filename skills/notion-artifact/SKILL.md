---
name: notion-artifact
description: Notion 페이지 룩의 HTML artifact 를 만든다. 팀 공유용 결정 문서, 비교표, 정리 노트에 쓴다. "노션 스타일로", "노션처럼", "notion artifact" 요청 시 사용.
---

# notion-artifact

Notion 페이지처럼 보이는 읽기용 artifact 를 만든다. UI 는 `notion.css` 하나로 끝내고, 나머지는 글의 구조와 문장에 쓴다.

## 언제 쓰나
- 팀 리드, 동료에게 공유할 결정 문서, As-is/To-be 비교, 조사 결과 정리
- 대시보드, 앱, 랜딩처럼 조작하는 페이지에는 쓰지 않는다

## 워크플로우
1. 내용 먼저 확정한다. 결론 1문장, 섹션 3개 이내, 접을 것과 펼칠 것을 나눈다 (아래 "글 규칙").
2. `references/writing-rules.md` 를 읽는다. 쓰기 전에 읽는다. 쓰고 나서 고치는 것보다 싸다.
3. `template.html` 을 복사하고 `notion.css` 전체를 `<style>` 에 인라인한다. 외부 CSS 링크는 CSP 에 막힌다.
4. 블록 매핑표대로 HTML 을 채운다. 새 클래스를 만들지 않는다.
5. **검증 루프를 돈다 (아래 "검증 게이트"). 통과 전에는 publish 하지 않는다.**
6. Artifact 도구로 publish 한다. 제목은 `<title>` 에 2~4 단어 명사구.

## 검증 게이트

파일을 쓴 다음, publish 전에 반드시 돈다.

```
python3 <스킬폴더>/lint.py <작성한 파일>.html
```

스킬 폴더는 보통 `~/.claude/skills/notion-artifact` 다.

- **종료 코드 0 이 아니면 publish 금지.** 예외 없다.
- 보고된 항목을 **전부** 고친다. 골라서 고치지 않는다. 각 항목은 `규칙ID  줄  «발췌» → 처방` 형식이고, 규칙 ID 는 `references/writing-rules.md` 에서 찾는다.
- 고쳤으면 **다시 실행한다.** 한 곳을 고치면 다른 규칙이 새로 걸린다. 0건이 나올 때까지 반복한다.
- 고치다가 내용이 바뀌면 안 된다. 수치, 고유명사, 결론은 그대로 두고 문장만 바꾼다. 문장을 못 살리겠으면 그 문장을 지운다.
- **용어를 번역하지 않는다.** `alias`, `promote`, `backfill`, `staging` 같은 기술 용어와 코드 식별자, 사내 용어는 원문 그대로 둔다. 고칠 대상은 용어가 아니라 그 주변 문장이다 (writing-rules 0절).
- 진짜 오탐이면 `--ignore K-27` 로 빼되, **어떤 규칙을 왜 뺐는지 사용자에게 보고한다.** 말없이 빼지 않는다.
- 5회 돌아도 0건이 안 되면 멈추고 남은 항목을 사용자에게 그대로 보여준다.

린터가 못 잡는 것(결론이 진짜 결론인지, 표의 축, 예시의 실재성)은 `writing-rules.md` 4절 체크리스트로 직접 확인한다.

린터 자체는 `python3 lint.py --selftest` 로 검증한다. 규칙 57개의 예문 검출과 정상 문서 오탐 0건을 확인한다.

## 블록 매핑
| Notion 블록 | HTML | 비고 |
|---|---|---|
| 페이지 제목, 아이콘 | `<h1 class="title">`, `<span class="title-icon">` | 40px |
| 헤딩 1, 2, 3 | `<h1>` `<h2>` `<h3>` | 30 / 24 / 20px. 부제는 `<small>` |
| 텍스트 | `<p>` | 한 문단 한 생각 |
| 불렛, 번호 | `<ul>` `<ol>` 중첩 | 2단까지. 마커 disc → circle → square 자동 |
| 콜아웃 | `<div class="callout [blue|yellow|red|green|outline]"><span class="icon">📌</span><div>…</div></div>` | 결론, 주의, 확인에만 |
| 토글 | `<details><summary>…</summary><div class="body">…</div></details>` | 헤딩 토글은 `class="h2"` `"h3"` |
| 표 | `<div class="tbl"><table>` | 첫 열 `td.k`, 숫자 열 `td.n` |
| 코드 블록 | `<pre><code>` | 주석 `.c`, 새 값 `.hl`, 이전 값 `.old` |
| 인라인 코드 | `<code>` | 필드명, 값, 경로 |
| 인용 | `<blockquote>` | |
| 구분선 | `<hr>` | 본문과 토글 사이 |
| 2열 | `<div class="row"><div class="col">…</div><div class="col">…</div></div>` | 640px 아래 1열 |
| 색 태그 | `<span class="pill bg-orange">A</span>` | 유형 라벨 |

## 레이아웃 규칙
- 상단에 결론 콜아웃 1개. 메타(작성일, 출처, 상위 문서)는 넣지 않는다. 필요하면 토글 안 `.dim` 한 줄.
- 펼친 본문은 3섹션 이내. 그 이하 상세는 전부 `<details>` 로 접는다.
- 표는 열 4개 이내, 행 8개 이내. 넘으면 토글로 내리거나 나눈다.
- 예시(실제 응답값, 코드)는 각 섹션 끝에 1개. 설명 문장보다 예시 하나가 낫다.
- 테마는 CSS 가 처리한다. 색을 직접 쓰지 않는다.

## 글 규칙
`references/writing-rules.md` 를 읽고 따른다. 규칙마다 ID 가 있고 `lint.py` 가 같은 ID 로 검출한다.

- **F** 서식, AI 말투 (humanizer, Wikipedia Signs of AI writing)
- **K** 한국어 문장 (im-not-ai 40패턴, toss/technical-writing, DaleSeo/korean-skills, 이오덕, 김정선)
- **S** 구조, 표, 불렛 (Google, Microsoft, NN/G, GOV.UK, Amazon 6-pager)
- **H** 린터가 못 잡는 것. 사람이 확인한다

용어는 원문, 문장은 한국어다. 기술 용어와 사내 용어를 한국어로 바꾸지 않는다 (0절).

자주 걸리는 것:
- 굵게, 기울임, 이모지 헤더, 대시, 가운뎃점 금지. 강조는 위치와 콜아웃으로.
- 결론이 첫 화면. 펼친 섹션 3개 이내, 상세는 토글.
- 불렛은 2단까지. 상위는 명사구 라벨, 하위에 사실. 같은 층은 같은 문형.
- 표는 행당 값 3개 이상일 때만. 열 4, 행 8 이내, 셀은 한 줄.
- 한 문장 한 생각, 40~50자. "~에 대해", 이중 피동, "~할 수 있다" 남발, "~것이다" 금지.
- 같은 개념은 한 이름. 코드 식별자는 `<code>`.

## 체크리스트

기계 검증(`lint.py`)이 F, K, S 규칙을 전부 본다. 사람이 볼 것은 이것뿐이다.

- [ ] 첫 콜아웃이 요약이 아니라 독자가 내려야 할 판단인가
- [ ] 표의 축이 독자의 결정 기준인가
- [ ] 예시의 값과 코드가 실재하는가 (지어내지 않았는가)
- [ ] 기술 용어를 원문 그대로 뒀는가
- [ ] 측정값과 추정을 구분했는가
- [ ] 접은 것과 펼친 것을 의식적으로 골랐는가
- [ ] 다크 모드에서 읽히는가
- [ ] `lint.py` 가 0건인가
