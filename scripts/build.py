#!/usr/bin/env python3
"""후처리 빌드 (365raeon.co.kr · beomeorosee.co.kr): 배포 폴더(content/site.json의 dist)의 글·허브·목록 페이지에
① 새론이치과 홈과 통일한 헤더·푸터(chrome) ② 오른쪽 퀵메뉴(quickmenu.html) ③ 추가 정보(tools/extra_info.py)를 반영한다.
홈(index.html)은 tools/build_home.py가 content/home.json으로 생성하며 여기서는 ②③만 적용한다.
글 발행: tools/wp_static_site.py publish <slug> → 그 다음 이 스크립트 실행."""
import json, re, subprocess, sys, pathlib
from html import escape as E
ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / 'content' / 'site.json').read_text(encoding='utf-8'))
DIST = ROOT / CFG['dist']
HOME = json.loads((ROOT / 'content' / 'home.json').read_text(encoding='utf-8')) if (ROOT / 'content' / 'home.json').exists() else None
CS, CE = '<!-- chrome:start -->', '<!-- chrome:end -->'
FS, FE = '<!-- chrome-footer:start -->', '<!-- chrome-footer:end -->'


def chrome_html():
    H = HOME; kw, brand = H['keyword'], H['brand']; logo = H['logo']
    head_css = '<link rel="stylesheet" href="/site-chrome.css">'
    header = (f'{CS}<div class="sh-utility"><div class="sh-wrap"><span>{E(H["utility"])}</span><a href="tel:{H["tel_href"]}">{E(H["tel"])}</a></div></div>'
              f'<header class="sh-header"><div class="sh-wrap"><a class="sh-brand" href="/" aria-label="{E(kw)} {E(brand)} 홈"><span class="sh-keyword">{E(kw)}</span><span class="sh-bar" aria-hidden="true"></span>'
              f'<img src="{logo["src"]}" alt="" width="40" height="40"><span class="sh-name">{E(brand)}</span></a>'
              f'<a class="sh-official" href="{H["official"]}" target="_blank" rel="noopener noreferrer">{E(kw)} 공식 홈페이지</a></div></header>{CE}')
    f = H['footer']
    footer = (f'{FS}<footer class="sh-footer"><div class="sh-wrap"><div class="sh-footer-top"><div><h2>{E(brand)}</h2>' + ''.join(f'<p>{E(p)}</p>' for p in f['lines']) +
              f'<p>대표전화 <a href="tel:{H["tel_href"]}">{E(H["tel"])}</a></p></div><div class="sh-footer-links">' +
              ''.join(f'<a href="{l["url"]}" target="_blank" rel="noopener">{E(l["text"])}</a>' for l in f['links']) +
              f'<a href="/blog/">건강정보 전체 글</a></div></div><div class="sh-disclaimer">{E(H["disclaimer"])}</div></div></footer>'
              f'<div class="sh-mobile-call"><a href="tel:{H["tel_href"]}">전화 문의</a><a href="{H["map"]}" target="_blank" rel="noopener">네이버 예약</a></div>{FE}')
    return head_css, header, footer


def apply_chrome():
    if not HOME: return 0
    head_css, header, footer = chrome_html()
    theme = HOME.get('theme', {})
    css = (ROOT / 'site-chrome.css').read_text(encoding='utf-8')
    css = ':root{--sh-blue:%s;--sh-navy:%s;--sh-line:%s;--sh-ink:#162e3c}\n' % (theme.get('--blue', '#0074aa'), theme.get('--navy', '#133c54'), theme.get('--line', '#dce5eb')) + css
    (DIST / 'site-chrome.css').write_text(css, encoding='utf-8')
    n = 0
    for p in DIST.rglob('*.html'):
        if p == DIST / 'index.html' or p.name == '404.html': continue
        s = p.read_text(encoding='utf-8', errors='replace'); o = s
        # 기존 템플릿 헤더/퀵바/홈링크/푸터 제거 (최초 1회), 이미 chrome이 있으면 교체
        s = re.sub(re.escape(CS) + r'.*?' + re.escape(CE), '', s, flags=re.S)
        s = re.sub(re.escape(FS) + r'.*?' + re.escape(FE), '', s, flags=re.S)
        s = re.sub(r'<header class="site-header">.*?</header>\s*', '', s, count=1, flags=re.S)
        s = re.sub(r'<nav class="quick"[^>]*>.*?</nav>\s*', '', s, count=1, flags=re.S)
        s = re.sub(r'<div class="wrap">\s*<div class="homelink">.*?</div>\s*</div>\s*', '', s, count=1, flags=re.S)
        s = re.sub(r'<footer>.*?</footer>\s*', '', s, count=1, flags=re.S)
        if head_css not in s: s = s.replace('</head>', head_css + '</head>', 1)
        s = s.replace('<body>', '<body>' + header, 1) if '<body>' in s else s
        s = s.replace('</body>', footer + '</body>', 1)
        if s != o: p.write_text(s, encoding='utf-8'); n += 1
    return n


def apply_quickmenu():
    f = ROOT / 'quickmenu.html'
    if not f.exists(): return 0
    frag = f.read_text(encoding='utf-8'); n = 0
    for p in DIST.rglob('*.html'):
        s = p.read_text(encoding='utf-8', errors='replace')
        s2 = re.sub(r'<!-- quickmenu:start -->.*?<!-- quickmenu:end -->', '', s, flags=re.S)
        if '</body>' in s2: s2 = s2.replace('</body>', frag + '</body>', 1)
        if s2 != s: p.write_text(s2, encoding='utf-8'); n += 1
    return n


if __name__ == '__main__':
    print(json.dumps({'chrome_changed': apply_chrome(), 'quickmenu_changed': apply_quickmenu()}, ensure_ascii=False))
    t = ROOT / 'tools' / 'extra_info.py'
    if t.exists(): subprocess.run([sys.executable, '-I', str(t), 'apply'], check=False)
