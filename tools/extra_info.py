#!/usr/bin/env python3
"""추가 정보·백링크 관리 도구 (정적 사이트용).

설정: content/extra-info.json          — 규칙 목록(적용 범위·설명·링크·순서·공개)
상태: content/extra-info-state.json    — 페이지별 렌더 해시·수정 시각(실제 변경된 페이지만 갱신)
출력: dist/**/*.html 의 본문 하단(관련 사이트 안내 앞)에 <section class="extra-info"> 삽입.
      등록 내용이 없는 페이지에는 영역을 넣지 않음. 생성기(build.py) 끝에서 `apply`가 자동 실행됨.

명령:
  apply                         규칙을 dist에 반영(멱등). 변경된 페이지 수·수정 URL 출력
  list                          규칙 목록
  add --scope all|articles|/a/,/b/ --text 문구 --url URL [--desc 설명] [--order N] [--private] [--allow-dup] [--skip-if-present]
  edit <id> [--desc ..] [--public|--private] [--order N] [--scope ..]
  remove <id>
  link-add <id> --text 문구 --url URL [--order N] [--allow-dup]
  link-remove <id> --url URL
  preview <path>                해당 페이지에 들어갈 HTML 미리보기(파일에는 쓰지 않음)
  pages                         적용 대상 페이지 목록(전체 페이지 = 홈 + og:type article 페이지)
  report                        페이지별 링크 목록·수정 시각·중복·형식 오류 정리
"""
import argparse, hashlib, json, re, sys, datetime
from pathlib import Path
from html import escape as E

ROOT = None
MARK_S, MARK_E = '<!-- extra-info:start -->', '<!-- extra-info:end -->'
CSS = ('<style>.extra-info{margin:36px 0 8px;padding:20px 22px;border:1px solid #e3e3e3;border-radius:12px;background:#fafafa;font-size:15px;line-height:1.7}'
       '.extra-info h2{margin:0 0 10px;font-size:17px}.extra-info p{margin:0 0 10px}.extra-info ul{display:flex;flex-wrap:wrap;gap:6px 16px;list-style:none;margin:0;padding:0}'
       '.extra-info li{margin:0;word-break:keep-all}.extra-info a{text-decoration:underline}@media(max-width:600px){.extra-info{padding:16px;font-size:14px}}</style>')
KST = datetime.timezone(datetime.timedelta(hours=9))


def now():
    return datetime.datetime.now(KST).replace(microsecond=0).isoformat()


def site_cfg():
    p = ROOT / 'content' / 'site.json'
    try: return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except Exception: return {}


def dist_dir(): return ROOT / site_cfg().get('dist', 'dist')


def cfg_path(): return ROOT / 'content' / 'extra-info.json'
def state_path(): return ROOT / 'content' / 'extra-info-state.json'


def load_cfg():
    p = cfg_path()
    if not p.exists(): return {'version': 1, 'rules': []}
    return json.loads(p.read_text(encoding='utf-8'))


def save_cfg(c):
    cfg_path().parent.mkdir(parents=True, exist_ok=True)
    cfg_path().write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_state():
    p = state_path()
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def save_state(s):
    state_path().write_text(json.dumps(s, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def origin():
    s = (dist_dir() / 'index.html').read_text(encoding='utf-8', errors='replace')
    m = re.search(r'<link rel="canonical" href="(https?://[^/"]+)', s)
    return m.group(1) if m else ''


def page_path(f: Path) -> str:
    rel = f.relative_to(dist_dir()).as_posix()
    if rel == 'index.html': return '/'
    if rel.endswith('/index.html'): return '/' + rel[:-len('index.html')]
    return '/' + rel


def target_pages():
    """전체 페이지 = 홈 + og:type=article 페이지 (목록·404 제외)."""
    out = []
    marker = site_cfg().get('article_marker')  # 예: '<h1 class="ph">' — og:type 대신 글 페이지를 식별할 문자열
    for f in sorted(dist_dir().rglob('*.html')):
        rel = f.relative_to(dist_dir()).as_posix()
        if rel == '404.html': continue
        s = f.read_text(encoding='utf-8', errors='replace')
        if rel == 'index.html' or (marker and marker in s) or (not marker and ('og:type" content="article"' in s or "og:type' content='article'" in s)):
            out.append((page_path(f), f))
    return out


def norm_scope(scope):
    if scope in ('all', ['all']): return 'all'
    if scope in ('articles', ['articles']): return 'articles'  # 홈 제외, 모든 글·가이드 페이지
    if isinstance(scope, str): scope = [x.strip() for x in scope.split(',') if x.strip()]
    out = []
    for p in scope:
        p = re.sub(r'^https?://[^/]+', '', p) or '/'
        if not p.startswith('/'): p = '/' + p
        if not p.endswith('/') and not p.endswith('.html'): p += '/'
        out.append(p)
    return out


def rule_applies(rule, path):
    if not rule.get('public', True): return False
    sc = rule.get('scope', 'all')
    if sc == 'articles': return path != '/'
    return sc == 'all' or path in sc


def page_hrefs(html):
    return {h.rstrip('/') for h in re.findall(r'href="([^"]+)"', strip_block(html))}


def render(path, cfg, html=None):
    """html을 주면 skip_if_present 규칙의 링크 중 페이지 원본에 이미 있는 URL은 건너뜀(기존 링크 유지·중복 방지)."""
    rules = [r for r in cfg['rules'] if rule_applies(r, path)]
    present = page_hrefs(html) if html is not None else set()
    descs, links = [], []
    for ri, r in enumerate(sorted(rules, key=lambda r: (r.get('order', 100), r.get('id', '')))):
        added = 0
        for li, l in enumerate(r.get('links', [])):
            if not l.get('public', True): continue
            if r.get('skip_if_present') and l['url'].rstrip('/') in present: continue
            links.append((r.get('order', 100), l.get('order', li + 1), l['text'], l['url'])); added += 1
        if r.get('description') and (added or not r.get('links')): descs.append(r['description'])
    if not descs and not links: return ''
    links.sort(key=lambda x: (x[0], x[1]))
    body = ''.join(f'<p>{E(d)}</p>' for d in descs)
    if links:
        body += '<ul>' + ''.join(f'<li><a href="{E(u, quote=True)}">{E(t)}</a></li>' for _, _, t, u in links) + '</ul>'
    return f'{MARK_S}{CSS}<section class="extra-info" aria-label="추가 정보"><h2>추가 정보</h2>{body}</section>{MARK_E}'


def strip_block(s):
    return re.sub(re.escape(MARK_S) + r'.*?' + re.escape(MARK_E), '', s, flags=re.S)


def inject(s, block):
    s = strip_block(s)
    if not block: return s
    for anchor in ('<section class="hospital-links', '</article>', '</main>', '</body>'):
        i = s.find(anchor)
        if i != -1:
            return s[:i] + block + s[i:]
    return s


def cmd_apply(_a):
    cfg, st = load_cfg(), load_state()
    changed, with_block, urls = [], 0, []
    o = origin()
    for path, f in target_pages():
        s = f.read_text(encoding='utf-8')
        block = render(path, cfg, s)
        s2 = inject(s, block)
        if block: with_block += 1
        h = hashlib.sha1(block.encode('utf-8')).hexdigest() if block else ''
        prev = st.get(path, {})
        if prev.get('hash', '') != h:
            st[path] = {'hash': h, 'modified': now()}
            changed.append(path); urls.append(o + path)
        if s2 != s: f.write_text(s2, encoding='utf-8')
    save_state(st)
    patch_sitemap(st, changed)
    print(f'[extra-info] pages={len(target_pages())} with_block={with_block} changed={len(changed)}')
    if urls:
        (ROOT / 'content' / 'extra-info-modified-urls.txt').write_text('\n'.join(urls) + '\n', encoding='utf-8')
        for u in urls[:20]: print('  modified:', u)
        if len(urls) > 20: print(f'  ... 외 {len(urls) - 20}건 (전체 목록: content/extra-info-modified-urls.txt)')


def patch_sitemap(st, changed):
    sm = dist_dir() / 'sitemap.xml'
    if not sm.exists() or not changed: return
    s = sm.read_text(encoding='utf-8')
    if '<lastmod>' not in s: return  # 사이트맵에 lastmod가 없는 사이트는 건드리지 않음
    o = origin()
    for p in changed:
        loc = re.escape(o + p)
        d = st[p]['modified'][:10]
        s, n = re.subn(r'(<url><loc>' + loc + r'</loc>)(<lastmod>[^<]*</lastmod>)?', r'\g<1>' + f'<lastmod>{d}</lastmod>', s, count=1)
    sm.write_text(s, encoding='utf-8')


def existing_links_in_page(f: Path):
    s = strip_block(f.read_text(encoding='utf-8', errors='replace'))
    return set(re.findall(r'href="([^"]+)"', s))


def find_dups(cfg, scope, url, exclude_id=None):
    """같은 URL이 이미 규칙에 있거나(겹치는 범위) 페이지 원본에 있으면 목록 반환."""
    dups = []
    for r in cfg['rules']:
        if r.get('id') == exclude_id: continue
        for l in r.get('links', []):
            if l['url'].rstrip('/') == url.rstrip('/'):
                rs = r.get('scope', 'all')
                if scope in ('all', 'articles') or rs in ('all', 'articles') or set(rs) & set(scope):
                    dups.append(f"규칙 {r['id']} ({'전체' if rs == 'all' else ','.join(rs)}) 에 같은 링크 있음")
    pages = target_pages()
    check = pages if scope == 'all' else ([(p, f) for p, f in pages if p != '/'] if scope == 'articles' else [(p, f) for p, f in pages if p in scope])
    hit = [p for p, f in check if url.rstrip('/') in {h.rstrip('/') for h in existing_links_in_page(f)}]
    if hit: dups.append(f'페이지 원본에 이미 같은 링크 있음: {len(hit)}곳 (예: {hit[:3]})')
    return dups


def valid_url(u):
    return bool(re.match(r'^(https?://[^\s<>"]+|tel:[0-9+\-]+|mailto:[^\s<>"]+)$', u))


def new_id(cfg):
    n = 1 + max([int(r['id'][1:]) for r in cfg['rules'] if re.match(r'^r\d+$', r.get('id', ''))] or [0])
    return f'r{n}'


def cmd_add(a):
    cfg = load_cfg(); scope = norm_scope(a.scope)
    if not valid_url(a.url): print('형식 오류: URL은 http(s)://… 형태여야 합니다 →', a.url); sys.exit(2)
    if scope not in ('all', 'articles'):
        known = {p for p, _ in target_pages()}
        missing = [p for p in scope if p not in known]
        if missing: print('대상 페이지 없음:', missing); sys.exit(2)
    dups = find_dups(cfg, scope, a.url)
    if dups and not a.allow_dup:
        print('중복 감지 — 추가하지 않았습니다. 추가하려면 --allow-dup:'); [print('  -', d) for d in dups]; sys.exit(3)
    r = {'id': new_id(cfg), 'scope': scope, 'description': a.desc or '', 'order': a.order, 'public': not a.private,
         'skip_if_present': bool(a.skip_if_present),
         'links': [{'text': a.text, 'url': a.url, 'order': 1, 'public': True}], 'created': now(), 'updated': now()}
    cfg['rules'].append(r); save_cfg(cfg)
    print('추가됨:', json.dumps(r, ensure_ascii=False))
    if dups: print('(중복 경고 무시하고 추가함)'); [print('  -', d) for d in dups]


def get_rule(cfg, rid):
    for r in cfg['rules']:
        if r['id'] == rid: return r
    print('규칙 없음:', rid); sys.exit(2)


def cmd_link_add(a):
    cfg = load_cfg(); r = get_rule(cfg, a.id)
    if not valid_url(a.url): print('형식 오류:', a.url); sys.exit(2)
    dups = find_dups(cfg, r.get('scope', 'all'), a.url)
    if dups and not a.allow_dup:
        print('중복 감지 — 추가하지 않았습니다. 추가하려면 --allow-dup:'); [print('  -', d) for d in dups]; sys.exit(3)
    order = a.order or (1 + max([l.get('order', 0) for l in r['links']] or [0]))
    r['links'].append({'text': a.text, 'url': a.url, 'order': order, 'public': True}); r['updated'] = now()
    save_cfg(cfg); print('링크 추가됨:', a.id, a.text, a.url)


def cmd_link_remove(a):
    cfg = load_cfg(); r = get_rule(cfg, a.id)
    before = len(r['links']); r['links'] = [l for l in r['links'] if l['url'] != a.url]; r['updated'] = now()
    save_cfg(cfg); print(f'링크 삭제: {before - len(r["links"])}건')


def cmd_edit(a):
    cfg = load_cfg(); r = get_rule(cfg, a.id)
    if a.desc is not None: r['description'] = a.desc
    if a.public: r['public'] = True
    if a.private: r['public'] = False
    if a.order is not None: r['order'] = a.order
    if a.scope: r['scope'] = norm_scope(a.scope)
    r['updated'] = now(); save_cfg(cfg); print('수정됨:', json.dumps(r, ensure_ascii=False))


def cmd_remove(a):
    cfg = load_cfg(); before = len(cfg['rules'])
    cfg['rules'] = [r for r in cfg['rules'] if r['id'] != a.id]; save_cfg(cfg)
    print(f'삭제: {before - len(cfg["rules"])}건')


def cmd_list(_a):
    cfg = load_cfg()
    if not cfg['rules']: print('(규칙 없음)'); return
    for r in cfg['rules']:
        sc = '전체' if r.get('scope') == 'all' else ('모든 글(홈 제외)' if r.get('scope') == 'articles' else f"{len(r['scope'])}페이지 {r['scope'][:3]}")
        print(f"{r['id']} [{'공개' if r.get('public', True) else '비공개'}] 범위={sc} 순서={r.get('order')} 설명={r.get('description') or '-'}")
        for l in sorted(r['links'], key=lambda l: l.get('order', 0)):
            print(f"    {l.get('order')}. {l['text']} → {l['url']}{'' if l.get('public', True) else ' (비공개)'}")


def cmd_preview(a):
    cfg = load_cfg(); p = norm_scope(a.path)[0]
    f = dist_dir() / (p.strip('/') + '/index.html' if p != '/' else 'index.html')
    b = render(p, cfg, f.read_text(encoding='utf-8') if f.exists() else None)
    print(b.replace(CSS, '') if b else '(이 페이지에는 표시할 추가 정보가 없습니다)')


def cmd_pages(_a):
    for p, _ in target_pages(): print(p)


def cmd_report(_a):
    cfg, st = load_cfg(), load_state(); o = origin()
    pages = target_pages(); rows = []
    for p, f in pages:
        html = f.read_text(encoding='utf-8', errors='replace')
        b = render(p, cfg, html)
        if not b: continue
        links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', b)
        inhtml = MARK_S in html
        rows.append((p, links, st.get(p, {}).get('modified', '-'), inhtml))
    print(f'적용 페이지 수: {len(rows)} / 대상 {len(pages)}')
    bad = [(r['id'], l['url']) for r in cfg['rules'] for l in r['links'] if not valid_url(l['url'])]
    if bad: print('형식 오류 링크:', bad)
    seen = {}
    for r in cfg['rules']:
        for l in r['links']: seen.setdefault(l['url'].rstrip('/'), []).append(r['id'])
    dup = {u: ids for u, ids in seen.items() if len(ids) > 1}
    if dup: print('규칙 간 중복 URL:', dup)
    for p, links, mod, inhtml in rows[:400]:
        print(f"{o}{p} | 수정 {mod} | 원본HTML {'포함' if inhtml else '미포함'} | " + ' ; '.join(f'{t}→{u}' for u, t in links))


def main():
    global ROOT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=None, help='저장소 루트(기본: 이 파일의 상위 폴더)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('apply'); sub.add_parser('list'); sub.add_parser('pages'); sub.add_parser('report')
    s = sub.add_parser('add'); s.add_argument('--scope', required=True); s.add_argument('--text', required=True); s.add_argument('--url', required=True)
    s.add_argument('--desc'); s.add_argument('--order', type=int, default=100); s.add_argument('--private', action='store_true'); s.add_argument('--allow-dup', action='store_true')
    s.add_argument('--skip-if-present', action='store_true', help='페이지 원본에 이미 같은 URL이 있으면 그 페이지에선 해당 링크 생략')
    s = sub.add_parser('edit'); s.add_argument('id'); s.add_argument('--desc'); s.add_argument('--public', action='store_true'); s.add_argument('--private', action='store_true'); s.add_argument('--order', type=int); s.add_argument('--scope')
    s = sub.add_parser('remove'); s.add_argument('id')
    s = sub.add_parser('link-add'); s.add_argument('id'); s.add_argument('--text', required=True); s.add_argument('--url', required=True); s.add_argument('--order', type=int); s.add_argument('--allow-dup', action='store_true')
    s = sub.add_parser('link-remove'); s.add_argument('id'); s.add_argument('--url', required=True)
    s = sub.add_parser('preview'); s.add_argument('path')
    a = ap.parse_args()
    ROOT = Path(a.root).resolve() if a.root else Path(__file__).resolve().parents[1]
    {'apply': cmd_apply, 'list': cmd_list, 'pages': cmd_pages, 'report': cmd_report, 'add': cmd_add, 'edit': cmd_edit,
     'remove': cmd_remove, 'link-add': cmd_link_add, 'link-remove': cmd_link_remove, 'preview': cmd_preview}[a.cmd](a)


if __name__ == '__main__':
    main()
