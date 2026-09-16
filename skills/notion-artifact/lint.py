#!/usr/bin/env python3
"""notion-artifact 산출물 기계 검증기. stdlib 만 쓴다.

사용:
    python3 lint.py page.html
    python3 lint.py page.html --type=procedure     # 유형 자동 판정을 덮어쓴다
    python3 lint.py page.html --ignore K-12,S-05
    python3 lint.py --selftest

문서 유형(procedure / decision / reference / note)을 HTML 표면 신호로 판정하고
유형별로 다른 구조 규칙을 건다. 확신이 없으면 note 로 떨어뜨린다.

종료 코드: 0 통과 · 1 위반 · 2 사용법 오류
규칙 ID 는 references/writing-rules.md 의 절 번호와 1:1 로 맞춘다.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser

# ---------------------------------------------------------------- 파서

SKIP_TAGS = {"script", "style", "pre", "code"}
CODE_MARK = "\x00"   # code/pre 가 있던 자리. 본문 규칙에 걸리지 않게 비출력 문자를 쓴다
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th",
              "summary", "blockquote", "figcaption", "div"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass
class Block:
    tag: str
    line: int
    text: str
    in_details: bool
    in_table: bool


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.title = ""
        self.flow: list[tuple[str, int, bool]] = []   # (kind, line, 접힘) 본문 순서
        self.headings: list[tuple[int, str, bool, int]] = []
        self.tables: list[dict] = []
        self.lists: list[dict] = []
        self.emphasis: list[tuple[str, int]] = []
        self.figures: list[list] = []   # [line, figcaption 있음]
        self.has_toc = False
        self._is_title = False
        self.pre = 0
        self.step_details: list[int] = []   # 절차 단계 안에 접힌 토글
        self.hr = 0
        self.max_details = 0
        self.max_list = 0
        self._skip = 0
        self._icon = 0
        self._in_title = False
        self._stack: list[Block] = []
        self._details = 0
        self._callout = 0
        self._tables: list[dict] = []
        self._lists: list[dict] = []
        self._cell: Block | None = None

    # -- 내부
    def _fl(self, kind: str, line: int) -> None:
        self.flow.append((kind, line, self._details > 0))

    def _flush(self) -> None:
        b = self._stack.pop()
        b.text = re.sub(r"\s+", " ", b.text).strip()
        if b.text:
            self.blocks.append(b)
        if self._lists and b.tag == "li":
            self._lists[-1]["items"].append(b.text)
        if self._tables and b.tag in ("td", "th"):
            self._tables[-1]["cells"][-1].append(b.text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        line = self.getpos()[0]
        if tag in SKIP_TAGS:
            if tag == "pre":
                self.pre += 1
                self._fl("body", line)
            if self._stack and not self._skip:
                self._stack[-1].text += CODE_MARK   # code/pre 자리표시자
            self._skip += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "span" and "icon" in cls:
            self._icon += 1
            return
        if tag in ("b", "strong", "i", "em", "mark", "u"):
            self.emphasis.append((tag, line))
        if tag == "hr":
            self.hr += 1
        if tag == "details":
            self._details += 1
            self.max_details = max(self.max_details, self._details)
            if any(l["tag"] == "ol" for l in self._lists):
                self.step_details.append(line)
        if tag == "nav" and "toc" in cls:
            self.has_toc = True
        if tag == "figure":
            self.figures.append([line, False])
        if tag == "figcaption" and self.figures:
            self.figures[-1][1] = True
        if tag == "div" and "mermaid" in cls:
            self._fl("body", line)
            self.pre += 1                      # 도표도 시각 블록으로 센다
        if tag == "div" and "callout" in cls:
            self._callout += 1
            self._fl("callout", line)
        elif tag == "div" and self._callout:
            self._callout += 1              # 콜아웃 안의 본문 div
        if tag in HEADING_TAGS:
            level = int(tag[1])
            self._is_title = tag == "h1" and "title" in cls
            if not self._is_title:
                self._fl(tag, line)
        if tag in ("p", "table", "ul", "ol", "details", "blockquote") \
                and "sub" not in cls and "toc" not in cls:
            self._fl("body", line)
        if tag == "table":
            self._tables.append({"line": line, "cells": [], "spans": 0,
                                 "hidden": self._details > 0})
        if tag == "tr" and self._tables:
            self._tables[-1]["cells"].append([])
        if tag in ("td", "th") and self._tables:
            if a.get("colspan") or a.get("rowspan"):
                self._tables[-1]["spans"] += 1
        if tag in ("ul", "ol"):
            self._lists.append({"line": line, "tag": tag, "items": [],
                                "depth": len(self._lists) + 1,
                                "in_callout": self._callout > 0})
            self.max_list = max(self.max_list, len(self._lists))
        if tag in BLOCK_TAGS:
            self._stack.append(Block(tag, line, "", self._details > 0,
                                     bool(self._tables)))

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if tag == "title":
            self._in_title = False
            return
        if tag == "span":
            self._icon = max(0, self._icon - 1)
            return
        if tag == "div":
            self._callout = max(0, self._callout - 1)
        if tag == "details":
            self._details = max(0, self._details - 1)
        if tag == "table" and self._tables:
            self.tables.append(self._tables.pop())
        if tag in ("ul", "ol") and self._lists:
            self.lists.append(self._lists.pop())
        if tag in BLOCK_TAGS and self._stack and self._stack[-1].tag == tag:
            if tag in HEADING_TAGS and not self._is_title:
                b = self._stack[-1]
                self.headings.append((int(tag[1]),
                                      re.sub(r"\s+", " ", b.text).strip(),
                                      b.in_details, b.line))
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._skip or self._icon:
            return
        if self._stack:
            self._stack[-1].text += data


# ---------------------------------------------------------------- 문서 유형

# 한국어에서 명령형 어미는 절차의 신호가 못 된다. 기술 문서는 행동 유도도 "~한다"로
# 쓰고(카카오 가이드는 "~하세요"를 금지한다), 목록과 표는 개조식이라 어미가 아예 없다.
# 그래서 어미가 아니라 <ol> + 동사 어간 + 단계 안 코드로 판정한다.
STEP_V = re.compile(r"(실행|배포|확인|설정|재시작|롤백|적용|접속|입력|생성|삭제|수정|"
                    r"복사|중지|시작|머지|빌드|반영|교체|승인|점검|기동|내림|올림)")
DECIDE = re.compile(r"(결론|권장|제안|선택|대안|방안|트레이드오프|장단점|비교|근거|"
                    r"리스크|영향|결정|기로 한다|하기로|낫다|택한다|as[- ]?is|to[- ]?be)", re.I)
REF_W  = re.compile(r"(필드|파라미터|기본값|스키마|엔드포인트|옵션|환경 ?변수|설정값|"
                    r"스펙|타입|schema|spec|api)", re.I)
PROC_H = re.compile(r"(사전 ?조건|전제|준비|절차|단계|순서|롤백|검증|배포|점검|복구)")
# 장애 기록은 결론 콜아웃 없이 증상부터 시작하는 일이 많다. 헤딩 어휘로 잡는다
INCID  = re.compile(r"(증상|원인|영향|재발 ?방지|경위|타임라인|장애|해결)")
CLOCK  = re.compile(r"\b\d{1,2}:\d{2}\b")

TYPES = ("procedure", "decision", "reference", "note")


def doctype(p: Page) -> tuple[str, int]:
    """HTML 표면 신호로 문서 유형을 고른다. 확신이 없으면 note 로 떨어뜨린다."""
    ols = [l for l in p.lists if l["tag"] == "ol" and len(l["items"]) >= 3]
    items = [i for l in ols for i in l["items"]]
    cells = sum(len(r) for t in p.tables for r in t["cells"])
    body = max(1, sum(k == "body" for k, _, _ in p.flow))
    heads = " ".join(h[1] for h in p.headings)
    top = " ".join(b.text for b in p.blocks[:3])
    first = next((k for k, _, _ in p.flow if k in ("callout", "body")), "")

    s = {"procedure": 0, "decision": 0, "reference": 0, "note": 1}
    if ols:
        s["procedure"] += 3
        s["reference"] -= 2
    if items and sum(bool(STEP_V.search(i)) for i in items) / len(items) > .6:
        s["procedure"] += 2
    if items and sum(CODE_MARK in i for i in items) / len(items) > .4:
        s["procedure"] += 2
    if PROC_H.search(heads):
        s["procedure"] += 2

    if first == "callout" and DECIDE.search(top):
        s["decision"] += 3
    if DECIDE.search(heads):
        s["decision"] += 2
    if any(len(t["cells"]) >= 3 and DECIDE.search(" ".join(t["cells"][0]))
           for t in p.tables):
        s["decision"] += 2
    if INCID.search(heads):
        s["decision"] += 3      # 콜아웃 없이 시작하는 장애 기록을 건지려면 이만큼 필요하다
    if not ols:
        s["decision"] += 1

    if cells / body > .5:
        s["reference"] += 3
    if sum(len(t["cells"]) >= 4 for t in p.tables) >= 2:
        s["reference"] += 2
    if REF_W.search(heads):
        s["reference"] += 1
        if len(p.headings) >= 6:
            s["reference"] += 1

    kind = max(s, key=lambda k: s[k])
    return (kind, s[kind]) if s[kind] >= 4 else ("note", s[kind])


def is_incident(p: Page) -> bool:
    """장애 기록. decision 과 구조가 같아서 유형이 아니라 플래그로 둔다."""
    t = [b.text for b in p.blocks] + \
        [c for tb in p.tables for r in tb["cells"] for c in r]
    return sum(bool(CLOCK.search(x)) for x in t) >= 3


def sections(p: Page) -> list[tuple[int, int]]:
    """펼친 h2 마다 (줄, 본문 블록 수). 섹션 개수는 세지 않는다. 균형만 본다."""
    out: list[list[int]] = []
    for kind, line, hidden in p.flow:
        if hidden:
            continue
        if kind == "h2":
            out.append([line, 0])
        elif kind == "body" and out:
            out[-1][1] += 1
    return [(a, b) for a, b in out]


# ---------------------------------------------------------------- 규칙

@dataclass
class Finding:
    rule: str
    line: int
    excerpt: str
    fix: str

    def __str__(self) -> str:
        return f"{self.rule}  {self.line}행  «{self.excerpt}»\n         → {self.fix}"


EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF⬀-⯿]")

# 1회만 나와도 실패 (S1). 패턴은 활용형이 조합된 음절을 그대로 잡아야 한다
# ("되어지" 는 "되어진" 을 못 잡는다). 각 규칙은 CASES 의 예문으로 검증한다.
BANNED = [
    ("K-01", r"되어지|되어진|되어질|되어졌|지게 된|나뉘어|잊혀|불리워|보여지|보여질",
     "이중 피동. 능동이나 단일 피동으로. '판단되어진다' → '판단된다'"),
    ("K-02", r"에 있어", "'~에 있어(서)' → '~에서', '~을 볼 때'"),
    ("K-03", r"가지고 있|갖고 있|가지고 간다",
     "잉여 동사. '경쟁력을 가지고 있다' → '경쟁력이 강하다'"),
    ("K-04", r"결론적으로|요약하면|정리하면|정리하자면|시사하는 바|주목할 만|"
             r"의미가 크|본질적으로|핵심적으로|살펴보자|살펴보겠|알아보겠|이상입니다|"
             r"도움이 되|참고하시|기대해",
     "결산·예열 상투구. 통째로 삭제하고 결론을 바로 쓴다"),
    ("K-05", r"때다|때입니다|시점이다|시점입니다|지금이야말로|인 셈이|"
             r"라는 뜻이|다는 뜻이|하는 이유다|이유다\.",
     "결말 공식·도치 결산. 순방향 평서로 닫는다"),
    ("K-06", r"(기술|시대|시스템|플랫폼|데이터|이 문서|이 글|우리)(이|가|은|는)\s"
             r"[^.]{0,20}(보여준다|제공한다|가져온다|묻는다|부른다|말해준다|역할을 한)",
     "추상 주어 + 만능 동사. 사람·기관을 주어로 올리고 동사를 구체화"),
    ("K-07", r"이 문서에서는|아래에서 설명|앞서 설명|먼저 정리하면|다음과 같습니다|"
             r"크게 (두|세|네) 가지|다음과 같은 (점|이유|사항)",
     "메타 담화·열거 도입구. 삭제하고 본론부터"),
    ("K-08", r"좋은 질문|물론입니다|말씀하신 대로", "챗봇 잔재. 삭제"),
    ("K-09", r"가 아니라|것이 아니라|것은 아니다|을 넘어|를 넘어",
     "대비·범위상승 구문. 결론만 단언한다"),
    ("K-10", r"혁신적|획기적|압도적|전례 없|파격적|폭발적|엄청난|놀라운|강력한|치명적",
     "hype 어휘. 구체 수치로 환원. '압도적 성장' → '전년 대비 47% 성장'"),
    ("K-16", r"에 의해|에 의하여", "영어식 피동. 행위자를 주어로. 'A에 의해 생성' → 'A가 만든'"),
    ("K-19", r"는 점에서|는 점이다|주목할 점은|점에 있다",
     "형식명사 강조. 'X는 ~다' 직설로"),
    ("K-20", r"것이다|것입니다|할 것으로|것이었다", "'~것이다' 단정·미래형. '~다'로 끝낸다"),
    ("K-21", r"하는 것(을|이|은|에)|되는 것(을|이|은)|한 것이|할 것을",
     "형식명사 '것'. 동사로 환원. '측정하는 것이 필요하다' → '측정한다'"),
    ("K-26", r"매우|정말|상당히|굉장히|훨씬 더|아주 |너무 ", "강조 부사. 삭제하고 수치로"),
    ("K-27", r"수행|실시(하|한|해|했)|진행(하|한|해|했)|처리를 (하|한)|작업을 (하|한)",
     "불필요한 한자어. '삭제를 수행한다' → '삭제한다'"),
    ("K-28", r"그것(은|이|을)|이것(은|이|을)|이는 |그는 |그들(은|이)",
     "영어식 대명사 주어. 명사구로 복원하거나 생략"),
    ("K-40", r"잠식|청사진|적신호|경고등|신호탄|뿌리내|짓누|움켜|기록적",
     "사전 은유·상투구. 명제로 직역. '잠식한다' → '점유율을 뺏는다'"),
    ("K-35", r"\d{4}년 \d{1,2}월|\d{4}\.\d{1,2}\.\d{1,2}|\d{1,2}/\d{1,2}/\d{4}",
     "날짜 표기. 2026-09-16 한 형식으로"),
    ("K-37", r"[가-힣][:：]\s*$", "문장 끝 콜론. 영어식 도입 콜론을 빼고 평서로"),
    ("K-30", r"[가-힣](고|며|면서|지만|는데|아서|어서|여서|하여),",
     "연결어미 뒤 쉼표. 쉼표를 뺀다"),
    ("K-33", r"저희", "지칭 통일. '우리'로"),
]

# 문장 종결로만 판정하는 규칙 (조합 음절 때문에 단순 포함 검사로는 오탐·미탐이 난다)
HONORIFIC = re.compile(r"(니다|[아어]요|세요|네요|죠|군요|구요)\s*[.!?]?$")

# 빈도 초과부터 실패 (S2). scope: doc | block
DENSITY = [
    ("K-12", r"에 대해|에 대한|에 대하여", "doc", 1,
     "'~에 대해' → 목적격 조사 직결. 'X에 대해 분석' → 'X를 분석'"),
    ("K-13", r"를 통해|을 통해|를 통하여|을 통하여|를 통한|을 통한", "doc", 1,
     "'~를 통해' → '~로', '~해서', '~함으로써'로 분산"),
    ("K-14", r"관련하여|관련된|관련해서", "doc", 1,
     "'~와 관련된' → '~에', '~의'. 실제 관계를 동사로"),
    ("K-15", r"에 기반하여|에 기반한|바탕으로", "doc", 1,
     "'~에 기반하여' → '~로', '~을 보고'"),
    ("K-17", r"수 있", "doc", 2,
     "'~할 수 있다' 남발. 실제 가능성만 남기고 나머지는 단정으로"),
    ("K-18", r"를 위해|을 위해|기 위해|를 위한|을 위한", "doc", 1,
     "'~을 위해' 목적절 → '~려고', '~도록'"),
    ("K-22", r"적\s+[가-힣]", "block", 1,
     "'~적 N' 추상 체인 → 명사+명사나 풀어쓰기. '구조적 한계' → '구조의 한계'"),
    ("K-24", r"고 있", "doc", 1,
     "진행형 남발 → 단순 시제. '늘고 있다' → '늘었다'"),
    ("K-25", r"보인다|판단된다|여겨진다|예상된다|가능성이 있|것으로 보", "doc", 1,
     "완곡 중첩. 완곡 하나만 남기고 극성은 유지"),
    ("K-29", r"(많은|여러|다양한|몇몇|모든)\s*[가-힣]+들|[가-힣]{2,}들(이|을|은|의|과|에서)",
     "doc", 1, "불필요한 '-들'. 수식어·문맥이 복수를 말하면 뺀다"),
    ("K-39", r"[가-힣]\([A-Za-z][A-Za-z ]{2,}\)", "doc", 1,
     "한글+괄호 영어 병기는 첫 등장 1회만"),
]

CONJUNCTIONS = ("또한", "따라서", "즉", "게다가", "더불어", "나아가", "아울러",
                "하지만", "그러나", "한편", "그리고", "그래서")

GENERIC_HEADINGS = {"개요", "소개", "배경", "결론", "정리", "마무리", "기타",
                    "내용", "요약", "참고", "본문", "시작하기"}


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def check(src: str, ignore: set[str],
          dtype: str | None = None) -> tuple[list[Finding], str, int]:
    p = Page()
    p.feed(src)
    guess, score = doctype(p)
    dtype = dtype or guess
    out: list[Finding] = []
    conj_lines: list[tuple[int, str]] = []

    def add(rule: str, line: int, excerpt: str, fix: str) -> None:
        if rule not in ignore:
            out.append(Finding(rule, line, excerpt.replace(CODE_MARK, "`")[:60], fix))

    # ---- 서식 (F)
    for tag, line in p.emphasis:
        add("F-01", line, f"<{tag}>", "본문 강조 태그 금지. 강조는 위치와 콜아웃으로")
    markup = re.sub(r"(?s)<style.*?</style>|<pre.*?</pre>", "", src)
    for m in re.finditer(r"\*\*|__[가-힣A-Za-z]", markup):
        add("F-02", markup[:m.start()].count("\n") + 1, m.group(0),
            "마크다운 잔재. HTML 로 쓰고 강조 표기는 뺀다")
    for m in re.finditer(r'style="[^"]*(color|background)', markup):
        add("F-07", markup[:m.start()].count("\n") + 1, m.group(0),
            "인라인 색 지정 금지. 테마는 notion.css 가 처리한다")
    for b in p.blocks:
        for rx, rule, fix in (
            (EMOJI, "F-03", "이모지는 콜아웃 아이콘 1개만"),
            (re.compile(r"[—–]"), "F-04", "대시 연결어 금지. 마침표로 끊거나 쉼표·괄호"),
            (re.compile(r"[“”‘’]"), "F-06", "굽은 따옴표 대신 직선 따옴표"),
            (re.compile(r"[·•・ㆍ]"), "F-10",
             "가운뎃점 금지. 열거는 쉼표로, 제목의 구분은 문장이나 헤딩으로 나눈다"),
        ):
            m = rx.search(b.text)
            if m:
                add(rule, b.line, b.text, fix)
        if "→" in b.text and b.tag not in ("td", "th"):
            add("F-05", b.line, b.text, "화살표는 표 셀과 코드 주석 안에서만. 문장은 '에서 …로'")
    # ---- 구조 (S)
    words = p.title.split()
    if not (2 <= len(words) <= 4) or re.search(r"(다|요|까)[.?]?$", p.title.strip()):
        add("S-01", 1, p.title.strip() or "(없음)", "<title> 은 명사구 2~4 단어")
    n_title = len(re.findall(r'<h1[^>]*class="[^"]*title', src))
    if n_title != 1:
        add("S-02", 1, f"h1.title {n_title}개", "페이지 제목 h1.title 은 1개")
    kinds = [k for k, _, _ in p.flow]
    if dtype != "reference":
        if "callout" not in kinds:
            add("S-03", 1, "콜아웃 없음", "결론 콜아웃 1개를 첫 화면에 둔다")
        elif kinds[0] != "callout":
            add("S-03", p.flow[0][1], kinds[0], "첫 블록은 결론 콜아웃이어야 한다")
    if kinds.count("callout") > 3:
        add("S-03", 1, f"콜아웃 {kinds.count('callout')}개", "콜아웃은 결론 1 + 주의·확인 2 까지")
    secs = sections(p)
    if len(secs) >= 3:
        mid = sorted(n for _, n in secs)[len(secs) // 2]
        for line, n in secs:
            if mid >= 3 and n * 3 < mid:
                add("S-18", line, f"블록 {n}개 (중앙값 {mid})",
                    "쪼가리 섹션. 옆 섹션에 합치거나 문장으로 내린다")
            elif n > mid * 3 and n >= 6:
                add("S-18", line, f"블록 {n}개 (중앙값 {mid})",
                    "혼자 비대한 섹션. 나누거나 상세를 <details> 로 접는다")
    for t in p.tables:
        rows = [c for c in t["cells"] if c]
        cols = max((len(c) for c in rows), default=0)
        if cols > 4:
            add("S-05", t["line"], f"열 {cols}개", "표는 열 4개 이내. 넘으면 나눈다")
        if len(rows) - 1 > 8 and not t["hidden"]:
            add("S-05", t["line"], f"본문 행 {len(rows) - 1}개",
                "펼친 표는 행 8개 이내. 넘으면 <details> 로 접는다 (접힌 표는 제한 없음)")
        if cols < 2 or len(rows) < 2:
            add("S-06", t["line"], f"{len(rows)}행 {cols}열", "1행·1열 표 금지. 리스트로 푼다")
        if t["spans"]:
            add("S-06", t["line"], "colspan/rowspan", "병합 셀 금지. '동일', '해당 없음' 으로 채운다")
        for r in rows:
            for c in r:
                if not c:
                    add("S-06", t["line"], "(빈 셀)", "빈 셀 금지. '없음', '동일' 을 쓴다")
                elif len(c) > 40 or re.search(r"다[.?]$", c):
                    add("S-07", t["line"], c, "셀은 한 줄. 문장은 토글이나 본문으로 뺀다")
    for l in p.lists:
        n = len(l["items"])
        if n == 1:
            add("S-08", l["line"], l["items"][0], "항목 1개짜리 리스트 금지. 문장으로 푼다")
        if n > 7:
            add("S-08", l["line"], f"항목 {n}개", "리스트는 7개 이내. 묶어 상위 항목을 만든다")
        kinds_ = {bool(re.search(r"(다|요|음|함)[.]?$", i)) for i in l["items"] if i}
        if len(kinds_) > 1:
            add("S-10", l["line"], " / ".join(l["items"][:2]),
                "같은 리스트는 같은 문형. 전부 명사구이거나 전부 문장")
        for i in l["items"]:
            if re.match(r"^[^:：]{1,20}[:：]\s*\S", i):
                add("F-09", l["line"], i, "라벨+콜론 불렛 금지. 라벨이 필요하면 표로")
    if p.max_list > 2:
        add("S-09", 1, f"리스트 {p.max_list}단", "들여쓰기 2단까지. 3단은 헤딩이나 표로 승격")
    if p.max_details > 1:
        add("S-09", 1, f"토글 {p.max_details}단", "토글 안 토글 금지")
    if p.hr > 1:
        add("S-11", 1, f"<hr> {p.hr}개", "구분선은 본문과 접힌 상세 사이 1번만")
    prev = 1
    for level, text, _, line in p.headings:
        if level > 3:
            add("F-08", line, text, "헤딩은 H3 까지. 더 필요하면 페이지를 나눈다")
        if level > prev + 1:
            add("S-12", line, text, f"헤딩 레벨 건너뛰기(H{prev} → H{level})")
        prev = level
        if text.strip() in GENERIC_HEADINGS or text.strip().endswith("?"):
            add("S-13", line, text, "헤딩은 내용을 말하는 명사구. 일반 명칭·질문형 금지")
    for a, b in zip(p.flow, p.flow[1:]):
        if a[0].startswith("h") and b[0].startswith("h") and int(b[0][1]) <= int(a[0][1]):
            add("S-12", a[1], f"{a[0]} → {b[0]}", "헤딩 아래 내용 없이 헤딩이 이어진다")
    # ---- 구조, 유형별 (S-14 ~ S-20, P, D)
    body_n = max(1, sum(k == "body" for k, _, _ in p.flow))
    visual = len(p.tables) + p.pre
    cap = {"reference": 1.0, "procedure": .45}.get(dtype, .3)
    if visual / body_n > cap:
        add("S-19", 1, f"시각 블록 {visual}/{body_n} ({visual / body_n:.0%}, 한계 {cap:.0%})",
            "표, 코드, 도표가 본문을 덮는다. 설명 문단을 늘리거나 표를 합친다")
    for line, has_cap in p.figures:
        if not has_cap:
            add("S-20", line, "<figure>", "도표에는 <figcaption> 한 문장. 읽는 법을 말한다")
    for level, text, _, line in p.headings:
        if len(text) > 20:
            add("S-16", line, text, f"헤딩은 20자 이내. 지금 {len(text)}자")
        if level == 1 and dtype in ("note", "decision"):
            add("S-14", line, text, "본문 h1 금지. 페이지 제목은 h1.title 하나다")
    group: list[tuple[str, int]] = []
    for level, text, _, line in p.headings + [(2, "", False, 0)]:
        if level <= 2:
            if len(group) == 1:
                add("S-15", group[0][1], group[0][0],
                    "형제 없는 h3. 헤딩이 아니라 문장이거나, 짝이 빠졌다")
            group = []
        elif level == 3:
            group.append((text, line))
    open_h = [h for h in p.headings if not h[2]]
    if dtype == "reference" and len(open_h) >= 6 and not p.has_toc:
        add("S-17", 1, f"펼친 헤딩 {len(open_h)}개, 목차 없음",
            '참조 문서는 <nav class="toc"> 를 둔다 (template.html 참고)')
    heads_txt = " ".join([h[1] for h in p.headings]
                         + [b.text for b in p.blocks if b.tag == "summary"])
    if dtype == "procedure":
        for line in p.step_details:
            add("P-01", line, "<details>", "절차 단계 안 토글 금지. 접힌 단계는 건너뛴다")
        if not re.search(r"(롤백|되돌|복구|실패|rollback)", heads_txt, re.I):
            add("P-02", 1, "롤백 섹션 없음", "절차 문서에는 실패 시 되돌리는 방법을 넣는다")
    if dtype == "decision":
        alts = sum(len(t["cells"][0]) >= 3 for t in p.tables if t["cells"])
        alts += len(re.findall(r"(대안|방안|안 ?\d|옵션)", heads_txt))
        if alts < 1:
            add("D-01", 1, "대안 없음",
                "판단 문서는 비교 표(열 3개 이상)나 대안 섹션으로 선택지를 보인다")
    # ---- 콜아웃 (F-11, F-12)
    for l in p.lists:
        if l["in_callout"]:
            add("F-11", l["line"], " / ".join(l["items"][:2]),
                "콜아웃 안 불렛 금지. 콜아웃은 한두 문장이다. 목록은 본문으로 내린다")
    for a, b in zip(p.flow, p.flow[1:]):
        if a[0] == "callout" and b[0] == "callout":
            add("F-12", b[1], "callout + callout",
                "콜아웃 연속 금지. 사이에 본문을 두거나 하나로 합친다")
    # ---- 한국어 (K)
    for b in p.blocks:
        for rule, rx, fix in BANNED:
            for m in list(re.finditer(rx, b.text))[:3]:
                add(rule, b.line, b.text[max(0, m.start() - 12):m.end() + 12], fix)
        for rule, rx, scope, limit, fix in DENSITY:
            if scope == "block":
                n = len(re.findall(rx, b.text))
                if n > limit:
                    add(rule, b.line, b.text, f"{fix} (이 블록 {n}회)")
        if b.text.startswith(CONJUNCTIONS):
            conj_lines.append((b.line, b.text))
        for s in sentences(b.text):
            if HONORIFIC.search(s):
                add("K-32", b.line, s, "평서체 '~다'로 통일. 경어체 혼용 금지")
            if b.tag not in ("td", "th", "summary") and len(s) > 60:
                add("K-31", b.line, s, f"한 문장 한 생각, 40~50자. 지금 {len(s)}자")
    if len(conj_lines) > 2:
        add("K-23", conj_lines[2][0], conj_lines[2][1],
            f"문두 접속사 남발(문서 {len(conj_lines)}회, 허용 2회). 관계는 문장으로")
    joined = " ".join(b.text for b in p.blocks)
    for rule, rx, scope, limit, fix in DENSITY:
        if scope != "doc":
            continue
        n = len(re.findall(rx, joined, re.MULTILINE))
        if n > limit:
            add(rule, 1, f"문서 {n}회 (허용 {limit})", fix)
    endings = [m.group(0) for m in re.finditer(r"[가-힣]{2}(다|요)[.]", joined)]
    for i in range(len(endings) - 3):
        if len(set(e[:-1][-2:] for e in endings[i:i + 4])) == 1:
            add("K-34", 1, " ".join(endings[i:i + 4]), "같은 종결어미 4문장 연속. 종결을 변주한다")
            break
    units = re.findall(r"\d+\s?(?:건|개|명|원|초|분|시간|GB|MB|%)", joined)
    if units and len({" " in u for u in units}) > 1:
        add("K-36", 1, " / ".join(units[:4]), "숫자-단위 띄어쓰기를 한 방식으로 통일")
    if is_incident(p) and dtype in ("decision", "note"):
        # ponytail: 타임라인만 본다. 액션 아이템 담당·기한 검사는 오탐이 많아 뺐다
        if not re.search(r"(조치|후속|액션|재발 ?방지)", " ".join(h[1] for h in p.headings)):
            add("D-02", 1, "타임라인만 있고 후속 조치 없음",
                "장애 기록에는 재발 방지 또는 후속 조치 섹션을 넣는다")
    return out, dtype, score


# ---------------------------------------------------------------- CLI

def _parse(src: str) -> Page:
    p = Page()
    p.feed(src)
    return p


WRAP_BARE = '<html><head><title>가격 정책 변경</title></head><body>{}</body></html>'

WRAP = ('<html><head><title>가격 정책 변경</title></head><body>'
        '<h1 class="title">가격 정책</h1>'
        '<div class="callout blue"><span class="icon">📌</span><div>{}</div></div>'
        '{}</body></html>')

# 규칙마다 잡아야 하는 예문 하나. 패턴 활용형이 깨지면 여기서 먼저 터진다.
# 3번째 원소가 있으면 그 유형으로 강제한다 (유형별 규칙용)
CASES: list[tuple] = [
    ("K-01", "<p>결과가 도출되어진 값이다.</p>"),
    ("K-02", "<p>운영에 있어 문제가 남는다.</p>"),
    ("K-03", "<p>팀은 권한을 가지고 있다.</p>"),
    ("K-04", "<p>결론적으로 값이 바뀐다.</p>"),
    ("K-05", "<p>이제 바꿀 때다.</p>"),
    ("K-06", "<p>이 문서는 값의 변화를 보여준다.</p>"),
    ("K-07", "<p>이 문서에서는 두 축을 비교한다.</p>"),
    ("K-08", "<p>물론입니다.</p>"),
    ("K-09", "<p>속도가 아니라 정확도가 문제다.</p>"),
    ("K-10", "<p>혁신적 구조로 바꾼다.</p>"),
    ("K-12", "<p>알림에 대해 정리한다. 요금에 대한 설명을 넣는다.</p>"),
    ("K-13", "<p>스크립트를 통해 만든다. API를 통해 받는다.</p>"),
    ("K-14", "<p>요금과 관련된 값이다. 알림과 관련된 표다.</p>"),
    ("K-15", "<p>로그를 바탕으로 정한다. 지표를 바탕으로 본다.</p>"),
    ("K-16", "<p>스크립트에 의해 만들어진 값이다.</p>"),
    ("K-17", "<p>지울 수 있다. 바꿀 수 있다. 되돌릴 수 있다.</p>"),
    ("K-18", "<p>속도를 위해 캐시를 둔다. 안정을 위해 잠금을 쓴다.</p>"),
    ("K-19", "<p>값이 같다는 점에서 유지한다.</p>"),
    ("K-20", "<p>요금이 내려갈 것이다.</p>"),
    ("K-21", "<p>측정하는 것이 먼저다.</p>"),
    ("K-22", "<p>구조적 한계와 본질적 차이가 남는다.</p>"),
    ("K-23", "<p>값이 바뀐다.</p><p>또한 표를 나눈다.</p><p>따라서 토글로 접는다.</p>"
             "<p>그러나 결론은 같다.</p>"),
    ("K-24", "<p>값이 늘고 있다. 비용도 줄고 있다.</p>"),
    ("K-25", "<p>비용이 늘 것으로 보인다. 지연도 늘 가능성이 있다.</p>"),
    ("K-26", "<p>매우 빠른 응답이다.</p>"),
    ("K-27", "<p>삭제를 수행한다.</p>"),
    ("K-28", "<p>그것은 유지한다.</p>"),
    ("K-29", "<p>많은 사용자들이 쓴다. 기능들을 늘린다.</p>"),
    ("K-30", "<p>값을 지우고, 표를 나눈다.</p>"),
    ("K-31", "<p>이 값은 스크립트가 만든 기본 요금과 무료 한도와 알림 주기를 한 번에 "
             "바꾸는 유일한 경로여서 배포 순서와 캐시 무효화 시점을 지켜야 한다.</p>"),
    ("K-32", "<p>요금을 내립니다.</p>"),
    ("K-33", "<p>저희 팀이 쓴다.</p>"),
    ("K-34", "<p>값을 바꾼다. 표를 바꾼다. 토글을 바꾼다. 결론을 바꾼다.</p>"),
    ("K-35", "<p>2026년 9월에 바꾼다.</p>"),
    ("K-36", "<p>54건과 22 GB를 옮긴다.</p>"),
    ("K-37", "<p>바뀌는 값:</p>"),
    ("K-39", "<p>모델 엔지니어링(Model Engineering)과 자산 관리(Asset Management)다.</p>"),
    ("K-40", "<p>점유율을 잠식한다.</p>"),
    ("F-01", "<p>값이 <b>바뀐다</b>.</p>"),
    ("F-02", "<p>값이 **바뀐다**.</p>"),
    ("F-03", "<p>값이 바뀐다 🎉</p>"),
    ("F-04", "<p>요금 인하 — 무료 한도 확대.</p>"),
    ("F-05", "<p>12,000원 → 9,900원으로 내린다.</p>"),
    ("F-06", "<p>\u201c기본 요금\u201d을 내린다.</p>"),
    ("F-07", '<p style="color:#e33">값이 바뀐다.</p>'),
    ("F-08", "<h4>세부 값</h4><p>내용이 있다.</p>"),
    ("F-10", "<p>쿠키·세션·토큰을 지운다.</p>"),
    ("F-09", "<ul><li>요금: 9,900원으로 내린다</li><li>한도: 5건으로 늘린다</li></ul>"),
    ("S-05", "<table><tr><th>축</th><th>a</th><th>b</th><th>c</th><th>d</th></tr>"
             "<tr><td>기본</td><td>1</td><td>2</td><td>3</td><td>4</td></tr></table>"),
    ("S-06", "<table><tr><th>축</th><th>값</th></tr><tr><td>기본</td><td></td></tr></table>"),
    ("S-07", "<table><tr><th>축</th><th>값</th></tr><tr><td>기본</td>"
             "<td>기본 요금을 9,900원으로 내리고 무료 한도를 5건으로 늘린다.</td></tr></table>"),
    ("S-08", "<ul><li>한 항목</li></ul>"),
    ("S-09", "<ul><li>가<ul><li>나<ul><li>다</li></ul></li></ul></li></ul>"),
    ("S-10", "<ul><li>기본 요금 인하</li><li>무료 한도를 늘린다</li></ul>"),
    ("S-11", "<hr><p>값</p><hr>"),
    ("S-12", "<h1>큰 제목</h1><h3>작은 제목</h3><p>값</p>"),
    ("S-13", "<h2>개요</h2><p>값</p>"),
    ("S-14", "<h1>본문 제목</h1><p>값</p>", "decision"),
    ("S-15", "<h2>배포</h2><h3>혼자 있는 하위</h3><p>값</p><h2>정리</h2><p>값</p>"),
    ("S-16", "<h2>스물한 자를 넘기고도 남을 만큼 길게 늘어진 헤딩이다</h2><p>값</p>"),
    ("S-17", "<h2>가</h2><p>값</p><h2>나</h2><p>값</p><h2>다</h2><p>값</p>"
             "<h2>라</h2><p>값</p><h2>마</h2><p>값</p><h2>바</h2><p>값</p>", "reference"),
    ("S-18", "<h2>가</h2>" + "<p>값</p>" * 9 + "<h2>나</h2>" + "<p>값</p>" * 9
             + "<h2>다</h2><p>값</p>"),
    ("S-19", "<p>값</p><div class=\"tbl\"><table><tr><th>축</th><th>값</th></tr>"
             "<tr><td>기본</td><td>1</td></tr></table></div>"
             "<pre><code>x</code></pre><pre><code>y</code></pre>"),
    ("S-20", "<figure><div class=\"mermaid\">flowchart LR</div></figure><p>값</p>"),
    ("F-11", "<div class=\"callout\"><span class=\"icon\">📌</span><div>"
             "<ul><li>항목 하나</li><li>항목 둘</li></ul></div></div>"),
    ("F-12", "<div class=\"callout\"><span class=\"icon\">📌</span><div>첫 줄이다.</div></div>"
             "<div class=\"callout\"><span class=\"icon\">📌</span><div>둘째 줄이다.</div></div>"),
    ("P-01", "<h2>배포 절차</h2><ol><li>이미지를 빌드한다</li><li>staging 에 배포한다"
             "<details><summary>상세</summary><div class=\"body\"><p>값</p></div></details></li>"
             "<li>응답을 확인한다</li></ol>", "procedure"),
    ("P-02", "<h2>배포 절차</h2><ol><li>이미지를 빌드한다</li>"
             "<li>staging 에 배포한다</li><li>응답을 확인한다</li></ol>", "procedure"),
    ("D-01", "<h2>바꾸는 값</h2><p>기본 요금을 내린다.</p>", "decision"),
    ("D-02", "<h2>장애 경과</h2><ul><li>09:12 알림이 왔다</li><li>09:30 원인을 찾았다</li>"
             "<li>10:05 복구했다</li></ul>", "decision"),
]

# 유형 판정이 맞는지 보는 예문. 오분류는 규칙 오탐보다 비싸다
TYPE_CASES: list[tuple[str, str]] = [
    ("procedure",
     '<h1 class="title">배포</h1><h2>배포 절차</h2>'
     "<ol><li>이미지를 빌드한다 <code>make</code></li>"
     "<li>staging 에 배포한다 <code>helm</code></li>"
     "<li>응답을 확인한다 <code>curl</code></li></ol><h2>롤백</h2><p>이전 태그로 되돌린다.</p>"),
    ("decision",
     '<h1 class="title">요금</h1>'
     '<div class="callout blue"><span class="icon">📌</span><div>기본 요금을 내리기로 한다.</div></div>'
     "<h2>두 대안의 비교</h2><table><tr><th>축</th><th>A안</th><th>B안</th></tr>"
     "<tr><td>비용</td><td>1</td><td>2</td></tr></table>"),
    ("reference",
     '<h1 class="title">필드</h1><h2>요청 파라미터</h2>'
     "<table><tr><th>필드</th><th>타입</th><th>기본값</th><th>설명</th></tr>"
     "<tr><td>id</td><td>str</td><td>없음</td><td>식별자</td></tr>"
     "<tr><td>ttl</td><td>int</td><td>60</td><td>초</td></tr></table>"
     "<h2>응답 필드</h2><table><tr><th>필드</th><th>타입</th><th>기본값</th><th>설명</th></tr>"
     "<tr><td>ok</td><td>bool</td><td>true</td><td>성공</td></tr>"
     "<tr><td>msg</td><td>str</td><td>없음</td><td>메시지</td></tr></table>"),
    ("decision",   # 장애 기록. 콜아웃 없이 증상부터 시작한다
     '<h1 class="title">마운트 장애</h1>'
     "<h2>증상</h2><p>backend 가 저장소를 읽지 못한다.</p>"
     "<h2>원인</h2><p>기동 순서가 어긋났다.</p>"
     "<h2>재발 방지</h2><p>기동 전에 마운트를 확인한다.</p>"),
    ("note",
     '<h1 class="title">메모</h1>'
     '<div class="callout blue"><span class="icon">📌</span><div>값을 그대로 둔다.</div></div>'
     "<p>바꿀 이유가 없다.</p>"),
]

GOOD = """<html><head><title>가격 정책 변경</title></head><body>
<h1 class="title">가격 정책</h1>
<div class="callout blue"><span class="icon">📌</span><div>기본 요금을 9,900원으로 낮춘다.</div></div>
<h2>바뀌는 값</h2>
<div class="tbl"><table><tr><th>축</th><th>As-is</th><th>To-be</th></tr>
<tr><td class="k">기본 요금</td><td class="n">12,000원</td><td class="n">9,900원</td></tr>
<tr><td class="k">무료 한도</td><td class="n">3건</td><td class="n">5건</td></tr></table></div>
<p>인하폭은 17.5%다. 무료 한도는 두 건 늘린다.</p>
<h2>배포 순서</h2>
<ol><li>요금표 갱신</li><li>캐시 무효화</li><li>공지 발송</li></ol>
<h2>롤백</h2>
<p>이전 요금표로 되돌린다.</p>
<hr>
<details><summary>값 변화 54건 중 22건</summary><div class="body">
<p>나머지 32건은 동일하다.</p></div></details>
</body></html>"""


# 걸리면 안 되는 문서. 규칙을 조인 뒤 오탐이 나는 자리를 지킨다
CLEAN_CASES: list[tuple[str, str, str]] = [
    ("롤백이 토글 요약에 있는 절차",
     "<h2>배포 절차</h2><ol><li>이미지를 빌드한다</li><li>staging 에 배포한다</li>"
     "<li>응답을 확인한다</li></ol>"
     "<details><summary>롤백으로 안 돌아오는 것</summary>"
     "<div class=\"body\"><p>덤프를 restore 한다.</p></div></details>", "procedure"),
    ("대안이 토글 요약에 있는 판단 문서",
     "<h2>바꾸는 값</h2><p>기본 요금을 내린다.</p>"
     "<details><summary>검토한 대안 2개</summary>"
     "<div class=\"body\"><p>동결과 인상을 봤다.</p></div></details>", "decision"),
]


def selftest() -> None:
    missed = []
    for case in CASES:
        rule, body = case[0], case[1]
        forced = case[2] if len(case) > 2 else None
        found, _, _ = check(WRAP.format("결론 한 줄이다.", body), set(), forced)
        hits = {f.rule for f in found}
        if rule not in hits:
            missed.append((rule, sorted(hits)))
    assert not missed, "미검출 규칙: " + "; ".join(f"{r} (검출: {h})" for r, h in missed)

    wrong = []
    for want, doc in TYPE_CASES:
        got, sc = doctype(_parse(WRAP_BARE.format(doc)))
        if got != want:
            wrong.append(f"{want} 문서를 {got}({sc}점)로 봤다")
    assert not wrong, "유형 오분류: " + "; ".join(wrong)

    for name, doc, forced in CLEAN_CASES:
        extra, _, _ = check(WRAP.format("결론 한 줄이다.", doc), set(), forced)
        hit = [f for f in extra if f.rule in ("P-01", "P-02", "D-01", "D-02")]
        assert not hit, f"오탐({name}):\n" + "\n".join(map(str, hit))

    clean, dt, _ = check(GOOD, set())
    assert not clean, f"정상 문서({dt}) 오탐:\n" + "\n".join(map(str, clean))
    ignored, _, _ = check(WRAP.format("결론 한 줄이다.", "<p>값이 <b>바뀐다</b>.</p>"), {"F-01"})
    assert not any(f.rule == "F-01" for f in ignored), "--ignore 가 먹지 않는다"
    print(f"selftest 통과: 규칙 {len(CASES)}개 검출 · "
          f"유형 판정 {len(TYPE_CASES)}건 · 정상 문서 오탐 0건")


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        selftest()
        return 0
    paths = [a for a in argv if not a.startswith("--")]
    if len(paths) != 1:
        print(__doc__)
        return 2
    ignore: set[str] = set()
    for a in argv:
        if a.startswith("--ignore="):
            ignore |= {x.strip() for x in a.split("=", 1)[1].split(",") if x.strip()}
    if "--ignore" in argv and len(argv) > argv.index("--ignore") + 1:
        ignore |= {x.strip() for x in argv[argv.index("--ignore") + 1].split(",") if x.strip()}
    forced = None
    for a in argv:
        if a.startswith("--type="):
            forced = a.split("=", 1)[1].strip()
            if forced not in TYPES:
                print(f"없는 유형: {forced}. {', '.join(TYPES)} 중 하나를 쓴다.")
                return 2
    with open(paths[0], encoding="utf-8") as fh:
        src = fh.read()
    found, dtype, score = check(src, ignore, forced)
    how = "지정" if forced else f"{score}점"
    print(f"감지된 유형: {dtype} ({how})"
          + ("" if forced else "  틀렸으면 --type=<유형> 으로 지정한다"))
    if not found:
        print(f"통과: {paths[0]} 위반 0건")
        return 0
    order = {"F": 0, "S": 1, "K": 2}
    for f in sorted(found, key=lambda f: (order.get(f.rule[0], 3), f.rule, f.line)):
        print(f)
    print(f"\n위반 {len(found)}건. 전부 고치고 다시 실행한다. "
          f"오탐이면 --ignore 규칙ID 로 빼고 이유를 보고한다.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
