#!/usr/bin/env python3
"""notion-artifact 인라인 아이콘. 이름을 받아 <svg> 문자열을 뱉는다.

사용:
    python3 icon.py rocket              # <svg class="ico">…</svg>
    python3 icon.py triangle-alert c-red
    python3 icon.py --list              # 쓸 수 있는 이름과 용도

없는 이름은 종료 코드 1 로 실패한다. 아이콘 이름을 지어내지 않게 하려고 그렇게 만들었다.
출력은 그대로 HTML 에 붙인다. 색은 CSS 클래스로만 준다 (F-07: 인라인 색 금지).
도형은 currentColor 를 따르므로 다크 모드는 notion.css 가 알아서 맞춘다.

아이콘: Lucide v1.46.0 (ISC). NOTICE.md 참고.
"""

import sys

COLORS = ("c-gray", "c-blue", "c-orange", "c-green", "c-red", "c-purple")

# 이름: (용도, 내부 도형). viewBox 24x24, stroke 기반. 스타일은 .ico 가 준다
ICONS: dict[str, tuple[str, str]] = {
    'bug': (
        '버그, 결함',
        '<path d="M12 20v-9"/><path d="M14 7a4 4 0 0 1 4 4v3a6 6 0 0 1-12 0v-3a4 4 0 0 1 4-4z'
        '"/><path d="M14.12 3.88 16 2"/><path d="M21 21a4 4 0 0 0-3.81-4"/><path d="M21 5a4 4'
        ' 0 0 1-3.55 3.97"/><path d="M22 13h-4"/><path d="M3 21a4 4 0 0 1 3.81-4"/><path d="M'
        '3 5a4 4 0 0 0 3.55 3.97"/><path d="M6 13H2"/><path d="m8 2 1.88 1.88"/><path d="M9 7'
        '.13V6a3 3 0 1 1 6 0v1.13"/>'
    ),
    'circle-alert': (
        '장애, 오류',
        '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" '
        'x2="12.01" y1="16" y2="16"/>'
    ),
    'circle-check': (
        '확인 완료, 통과',
        '<circle cx="12" cy="12" r="10"/><path d="m16 9-5.5 5.5L8 12"/>'
    ),
    'circle-x': (
        '실패, 거절',
        '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>'
    ),
    'clock': (
        '일정, 소요 시간',
        '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>'
    ),
    'database': (
        '데이터, 저장소',
        '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d='
        '"M3 12A9 3 0 0 0 21 12"/>'
    ),
    'file-text': (
        '문서, 사양',
        '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2'
        '.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="M1'
        '0 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>'
    ),
    'flag': (
        '마일스톤, 기준점',
        '<path d="M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 '
        '1 20 4v10a1 1 0 0 1-.4.8A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528"/>'
    ),
    'git-branch': (
        '브랜치, 분기',
        '<path d="M15 6a9 9 0 0 0-9 9V3"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18'
        '" r="3"/>'
    ),
    'git-commit-horizontal': (
        '커밋, 리비전',
        '<circle cx="12" cy="12" r="3"/><line x1="3" x2="9" y1="12" y2="12"/><line x1="15" x2'
        '="21" y1="12" y2="12"/>'
    ),
    'info': (
        '참고, 배경',
        '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'
    ),
    'lightbulb': (
        '제안, 아이디어',
        '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.'
        '5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>'
    ),
    'list-checks': (
        '체크리스트, 절차',
        '<path d="M13 5h8"/><path d="M13 12h8"/><path d="M13 19h8"/><path d="m3 17 2 2 4-4"/>'
        '<path d="m3 7 2 2 4-4"/>'
    ),
    'lock': (
        '보안, 권한',
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 '
        '10 0v4"/>'
    ),
    'package': (
        '패키지, 아티팩트',
        '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0'
        ' 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><polyline point'
        's="3.29 7 12 12 20.71 7"/><path d="m7.5 4.27 9 5.15"/>'
    ),
    'rocket': (
        '배포, 릴리즈',
        '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/><path d="M4.5 16.5c-1.5 1.26-2 5-'
        '2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09"/><path d="M9 12a22'
        ' 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.4 22.4 0 0 1-4 2z"/><'
        'path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 .05 5 .05"/>'
    ),
    'scale': (
        '비교, 판단',
        '<path d="M12 3v18"/><path d="m19 8 3 8a5 5 0 0 1-6 0zV7"/><path d="M3 7h1a17 17 0 0 '
        '0 8-2 17 17 0 0 0 8 2h1"/><path d="m5 8 3 8a5 5 0 0 1-6 0zV7"/><path d="M7 21h10"/>'
    ),
    'search': (
        '조사, 분석',
        '<path d="m21 21-4.34-4.34"/><circle cx="11" cy="11" r="8"/>'
    ),
    'server': (
        '인프라, 환경',
        '<rect width="20" height="8" x="2" y="2" rx="2" ry="2"/><rect width="20" height="8" x'
        '="2" y="14" rx="2" ry="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.'
        '01" y1="18" y2="18"/>'
    ),
    'terminal': (
        '명령, 실행',
        '<path d="M12 19h8"/><path d="m4 17 6-6-6-6"/>'
    ),
    'trending-down': (
        '감소, 하락',
        '<path d="M16 17h6v-6"/><path d="m22 17-8.5-8.5-5 5L2 7"/>'
    ),
    'trending-up': (
        '증가, 개선',
        '<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/>'
    ),
    'triangle-alert': (
        '주의, 위험',
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
        '<path d="M12 9v4"/><path d="M12 17h.01"/>'
    ),
    'undo-2': (
        '롤백, 되돌리기',
        '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 '
        '5.5H11"/>'
    ),
    'users': (
        '팀, 담당자',
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><path d="M16 3.128a4 4 0 0 1 0 '
        '7.744"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/>'
    ),
    'wrench': (
        '수정, 작업',
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-'
        '.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7'
        '.057-8.259c.438.12.54.662.219.984z"/>'
    ),
}


def render(name: str, color: str = "") -> str:
    if name not in ICONS:
        raise KeyError(name)
    if color and color not in COLORS:
        raise ValueError(color)
    cls = "ico" + (" " + color if color else "")
    return (f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">'
            f'{ICONS[name][1]}</svg>')


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--list", "-l", "--help", "-h"):
        w = max(len(n) for n in ICONS)
        for n, (desc, _) in ICONS.items():
            print(f"  {n:<{w}}  {desc}")
        print(f"\n색: {', '.join(COLORS)} (생략하면 본문색)")
        return 0 if argv else 2
    name, color = argv[0], (argv[1] if len(argv) > 1 else "")
    try:
        print(render(name, color))
    except KeyError:
        print(f"없는 아이콘: {name}. --list 에 있는 이름만 쓴다.", file=sys.stderr)
        return 1
    except ValueError:
        print(f"없는 색: {color}. {', '.join(COLORS)} 중 하나를 쓴다.", file=sys.stderr)
        return 1
    return 0


def selftest() -> None:
    assert render("rocket").startswith('<svg class="ico" viewBox="0 0 24 24"')
    assert render("bug", "c-red").startswith('<svg class="ico c-red"')
    for n, (desc, shape) in ICONS.items():
        assert desc and shape.startswith("<") and shape.endswith(">"), n
        assert "style=" not in shape and "#" not in shape, n   # F-07: 색 하드코딩 금지
    try:
        render("nope"); raise AssertionError("없는 이름이 통과했다")
    except KeyError:
        pass
    print(f"selftest 통과: 아이콘 {len(ICONS)}개")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        sys.exit(main(sys.argv[1:]))
