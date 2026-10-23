#!/usr/bin/env python3
"""후처리 빌드: 배포 폴더(content/site.json의 dist)의 모든 HTML에 퀵메뉴(quickmenu.html)와 추가 정보(tools/extra_info.py)를 반영.
글 발행은 tools/wp_static_site.py publish <slug> 로 먼저 하고, 그 다음 이 스크립트를 실행한다."""
import json, re, subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / 'content' / 'site.json').read_text(encoding='utf-8'))
DIST = ROOT / CFG['dist']

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
    print(json.dumps({'quickmenu_changed': apply_quickmenu()}))
    t = ROOT / 'tools' / 'extra_info.py'
    if t.exists(): subprocess.run([sys.executable, '-I', str(t), 'apply'], check=False)
