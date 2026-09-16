#!/usr/bin/env python3
"""notion-artifact 산출물 기계 검증기. stdlib 만 쓴다.

사용:
    python3 lint.py page.html
    python3 lint.py page.html --ignore K-12,S-05
    python3 lint.py --selftest

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
        self.flow: list[tuple[str, int]] = []      # (kind, line) 본문 순서
        self.headings: list[tuple[int, str, bool, int]] = []
        self.tables: list[dict] = []
        self.lists: list[dict] = []
        self.emphasis: list[tuple[str, int]] = []
        self.hr = 0
        self.max_details = 0
        self.max_list = 0
        self._skip = 0
        self._icon = 0
        self._in_title = False
        self._stack: list[Block] = []
        self._details = 0
        self._tables: list[dict] = []
        self._lists: list[dict] = []
        self._cell: Block | None = None

    # -- 내부
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
                self.flow.append(("body", line))
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
        if tag == "div" and "callout" in cls:
            self.flow.append(("callout", line))
        if tag in HEADING_TAGS:
            level = int(tag[1])
            if not (tag == "h1" and "title" in cls):
                self.flow.append((tag, line))
        if tag in ("p", "table", "ul", "ol", "details", "blockquote", "pre") \
                and "sub" not in cls:
            self.flow.append(("body", line))
        if tag == "table":
            self._tables.append({"line": line, "cells": [], "spans": 0})
        if tag == "tr" and self._tables:
            self._tables[-1]["cells"].append([])
        if tag in ("td", "th") and self._tables:
            if a.get("colspan") or a.get("rowspan"):
                self._tables[-1]["spans"] += 1
        if tag in ("ul", "ol"):
            self._lists.append({"line": line, "tag": tag, "items": [],
                                "depth": len(self._lists) + 1})
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
        if tag == "details":
            self._details = max(0, self._details - 1)
        if tag == "table" and self._tables:
            self.tables.append(self._tables.pop())
        if tag in ("ul", "ol") and self._lists:
            self.lists.append(self._lists.pop())
        if tag in BLOCK_TAGS and self._stack and self._stack[-1].tag == tag:
            if tag in HEADING_TAGS:
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


def check(src: str, ignore: set[str]) -> list[Finding]:
    p = Page()
    p.feed(src)
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
    kinds = [k for k, _ in p.flow]
    if "callout" not in kinds:
        add("S-03", 1, "콜아웃 없음", "결론 콜아웃 1개를 첫 화면에 둔다")
    elif kinds[0] != "callout":
        add("S-03", p.flow[0][1], kinds[0], "첫 블록은 결론 콜아웃이어야 한다")
    if kinds.count("callout") > 3:
        add("S-03", 1, f"콜아웃 {kinds.count('callout')}개", "콜아웃은 결론 1 + 주의·확인 2 까지")
    open_h2 = [h for h in p.headings if h[0] == 2 and not h[2]]
    if len(open_h2) > 3:
        add("S-04", open_h2[3][3], open_h2[3][1], "펼친 섹션 3개 이내. 나머지는 <details> 로")
    for t in p.tables:
        rows = [c for c in t["cells"] if c]
        cols = max((len(c) for c in rows), default=0)
        if cols > 4:
            add("S-05", t["line"], f"열 {cols}개", "표는 열 4개 이내. 넘으면 나눈다")
        if len(rows) - 1 > 8:
            add("S-05", t["line"], f"본문 행 {len(rows) - 1}개", "표는 행 8개 이내. 넘으면 토글로")
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
    return out


# ---------------------------------------------------------------- CLI

WRAP = ('<html><head><title>가격 정책 변경</title></head><body>'
        '<h1 class="title">가격 정책</h1>'
        '<div class="callout blue"><span class="icon">📌</span><div>{}</div></div>'
        '{}</body></html>')

# 규칙마다 잡아야 하는 예문 하나. 패턴 활용형이 깨지면 여기서 먼저 터진다
CASES: list[tuple[str, str]] = [
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
    ("S-04", "<h2>가</h2><p>값</p><h2>나</h2><p>값</p><h2>다</h2><p>값</p>"
             "<h2>라</h2><p>값</p>"),
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
<hr>
<details><summary>값 변화 54건 중 22건</summary><div class="body">
<p>나머지 32건은 동일하다.</p></div></details>
</body></html>"""


def selftest() -> None:
    missed = []
    for rule, body in CASES:
        hits = {f.rule for f in check(WRAP.format("결론 한 줄이다.", body), set())}
        if rule not in hits:
            missed.append((rule, sorted(hits)))
    assert not missed, "미검출 규칙: " + "; ".join(f"{r} (검출: {h})" for r, h in missed)
    clean = check(GOOD, set())
    assert not clean, "정상 문서 오탐:\n" + "\n".join(map(str, clean))
    ignored = check(WRAP.format("결론 한 줄이다.", "<p>값이 <b>바뀐다</b>.</p>"), {"F-01"})
    assert not any(f.rule == "F-01" for f in ignored), "--ignore 가 먹지 않는다"
    print(f"selftest 통과: 규칙 {len(CASES)}개 검출 · 정상 문서 오탐 0건")


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
    with open(paths[0], encoding="utf-8") as fh:
        src = fh.read()
    found = check(src, ignore)
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
