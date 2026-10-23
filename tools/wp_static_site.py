#!/usr/bin/env python3
"""워드프레스 내보내기형 정적 사이트(365raeon.co.kr · beomeorosee.co.kr 템플릿) 발행 도구.

저장소 구조:
  content/site.json       사이트 설정(origin, dist, keyword, brand, author, 금지어 …)
  content/posts/<slug>.md 새 글(frontmatter: title, description(=lead), date, keyword, tags, og_image 선택)
  <dist>/                 배포 폴더(public 또는 docs). 기존 글은 <dist>/<한글슬러그>/index.html

명령:
  index                         기존 글 색인 출력(제목·날짜·슬러그), 글 수
  publish <slug>                content/posts/<slug>.md → 글 페이지 생성 + blog 목록/페이지 재구성 + sitemap + rss
  check <slug>                  발행 전 검수(분량·금지어·제목 중복·슬러그 중복). FAIL이면 발행 금지
  rebuild-lists                 blog/ 목록 페이지를 현재 글 색인으로 재생성(복구용)
"""
import argparse, json, re, sys, datetime, hashlib, random
from pathlib import Path
from html import escape as E
from urllib.parse import quote

KST = datetime.timezone(datetime.timedelta(hours=9))
ROOT = None; CFG = None; DIST = None

# ---------- 설정 ----------
def load():
    global CFG, DIST
    CFG = json.loads((ROOT / 'content' / 'site.json').read_text(encoding='utf-8'))
    DIST = ROOT / CFG['dist']

def origin(): return CFG['origin'].rstrip('/')

# ---------- 기존 글 색인 ----------
def is_post(html):
    return '<h1 class="ph">' in html and '<div class="pd">' in html

def post_index():
    """dist 안의 글 페이지 목록: [{slug,title,date,lead,path}] (날짜 내림차순, blog 목록 순서 우선)."""
    order = {}
    for p in sorted(DIST.glob('blog/**/index.html')):
        s = p.read_text(encoding='utf-8', errors='replace')
        for m in re.finditer(r'<article class="bitem">.*?<a href="/([^"/]+)/">', s, re.S):
            order.setdefault(m.group(1), len(order))
    posts = []
    for d in DIST.iterdir():
        f = d / 'index.html'
        if not d.is_dir() or not f.exists() or d.name in ('blog', 'about', 'contact', 'wp-content'): continue
        s = f.read_text(encoding='utf-8', errors='replace')
        if not is_post(s): continue
        title = re.search(r'<h1 class="ph">(.*?)</h1>', s, re.S).group(1).strip()
        dm = re.search(r'<div class="pd">(\d{4})년 (\d{2})월 (\d{2})일', s)
        date = f'{dm.group(1)}-{dm.group(2)}-{dm.group(3)}' if dm else '1970-01-01'
        lm = re.search(r'<p class="lead">(.*?)</p>', s, re.S)
        posts.append({'slug': d.name, 'title': title, 'date': date, 'lead': (lm.group(1).strip() if lm else ''), 'path': f,
                      'keyword': title.split()[0] if title else ''})
    posts.sort(key=lambda p: (p['date'], -order.get(p['slug'], 10**9)), reverse=True)
    return posts

# ---------- 마크다운 ----------
def parse_md(path):
    txt = path.read_text(encoding='utf-8')
    m = re.match(r'---\n(.*?)\n---\n(.*)$', txt, re.S)
    if not m: sys.exit('frontmatter 없음')
    fm = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, v = line.split(':', 1); v = v.strip()
            if v.startswith('"') and v.endswith('"'): v = v[1:-1]
            fm[k.strip()] = v
    body = m.group(2).strip()
    blocks = []
    for para in re.split(r'\n\s*\n', body):
        para = para.strip()
        if not para: continue
        if para.startswith('### '): blocks.append(('h3', para[4:].strip()))
        elif para.startswith('## '): blocks.append(('h2', para[3:].strip()))
        elif para.startswith('# '): continue
        else: blocks.append(('p', ' '.join(l.strip() for l in para.splitlines())))
    return fm, blocks

def body_html(blocks):
    out = []
    for t, text in blocks:
        if t == 'p': out.append(f'<p>{E(text)}</p>')
        else: out.append(f'<{t}>{E(text)}</{t}>')
    return '\n'.join(out)

def body_chars(blocks):
    return sum(len(re.sub(r'\s', '', t)) for k, t in blocks if k == 'p')

def make_slug(title):
    s = re.sub(r'[^\w가-힣\s-]', '', title)   # 문장부호 제거
    s = re.sub(r'\s+', '-', s.strip())
    return s[:80].strip('-')

# ---------- 검수 ----------
def trigram(s):
    s = re.sub(r'\s', '', s); return {s[i:i+3] for i in range(len(s) - 2)}

def cmd_check(a, quiet=False):
    md = ROOT / 'content' / 'posts' / f'{a.slug}.md'
    if not md.exists(): print('FAIL: 파일 없음', md); sys.exit(2)
    fm, blocks = parse_md(md); fails, warns = [], []
    title = fm.get('title', '').strip(); lead = fm.get('description', '').strip()
    kw = fm.get('keyword') or CFG['keyword']
    if not title: fails.append('title 없음')
    if not title.startswith(kw): fails.append(f'제목이 키워드({kw})로 시작하지 않음')
    if not (15 <= len(title) <= 45): warns.append(f'제목 길이 {len(title)} (권장 15~45)')
    if not (40 <= len(lead) <= 120): warns.append(f'description(lead) 길이 {len(lead)} (권장 40~120)')
    n = body_chars(blocks)
    lo, hi = CFG.get('min_chars', 1500), CFG.get('max_chars', 2500)
    if n < lo: fails.append(f'본문 {n}자 < {lo}')
    if n > hi + 300: warns.append(f'본문 {n}자 > {hi}')
    h2 = sum(1 for k, _ in blocks if k == 'h2')
    if h2 < 4: fails.append(f'h2 소제목 {h2}개 < 4')
    full = title + ' ' + lead + ' ' + ' '.join(t for _, t in blocks)
    for w in CFG.get('forbidden', []):
        if w in full: fails.append(f'금지어 포함: {w}')
    for pat in CFG.get('forbidden_patterns', []):
        if re.search(pat, full): fails.append(f'금지 표현: {pat}')
    if re.search(r'<[a-z]+[^>]*>', ' '.join(t for _, t in blocks)): fails.append('본문에 HTML 태그 있음')
    if re.search(r'https?://', full): fails.append('본문에 링크 있음')
    posts = post_index(); slug = fm.get('slug') or make_slug(title)
    if (DIST / slug).exists(): fails.append(f'슬러그 중복(이미 존재): {slug}')
    tt = trigram(title); tl = trigram(lead)
    for p in posts:
        if p['title'] == title: fails.append(f'제목 완전 중복: {p["slug"]}')
        sim = len(tt & trigram(p['title'])) / max(1, len(tt))
        if sim >= 0.6: warns.append(f'제목 유사 {sim:.2f}: {p["title"]}')
        if p['lead'] and len(tl & trigram(p['lead'])) / max(1, len(tl)) >= 0.5: warns.append(f'lead 유사: {p["slug"]}')
    if not quiet:
        print(f'slug={slug} title={title} chars={n} h2={h2}')
        for f in fails: print('FAIL:', f)
        for w in warns: print('WARN:', w)
        print('RESULT:', 'FAIL' if fails else 'PASS', f'(비교한 기존 글 {len(posts)}편)')
    return not fails, slug, fm, blocks

# ---------- 발행 ----------
def pick_og_image(posts, title):
    imgs = CFG.get('card_images') or []
    if not imgs:
        for p in posts[:60]:
            s = p['path'].read_text(encoding='utf-8', errors='replace')
            m = re.search(r'property="og:image" content="([^"]+)"', s)
            if m: imgs.append(m.group(1))
        imgs = list(dict.fromkeys(imgs))
    if not imgs: return origin() + '/wp-content/uploads/og-image.jpg'
    h = int(hashlib.md5(title.encode()).hexdigest(), 16)
    u = imgs[h % len(imgs)]
    return u if u.startswith('http') else origin() + u

def render_post(fm, blocks, slug, posts):
    tpl_post = posts[0]
    t = tpl_post['path'].read_text(encoding='utf-8')
    title = fm['title'].strip(); lead = fm.get('description', '').strip(); kw = fm.get('keyword') or CFG['keyword']
    date = fm.get('date', datetime.datetime.now(KST).strftime('%Y-%m-%d'))[:10]
    y, mo, d = date.split('-')
    suffix = CFG.get('title_suffix', f' | {kw}')
    full_title = title + suffix
    desc = (title + ' ' + lead).strip()[:160]
    og_img = fm.get('og_image') or pick_og_image(posts, title)
    url_raw = f'{origin()}/{slug}/'; url_enc = f'{origin()}/{quote(slug)}/'
    tags = fm.get('tags', '').strip()
    tags_html = ' '.join('#' + x.strip().lstrip('#') for x in re.split(r'[,\s]+', tags) if x.strip()) if tags else f'#{kw}'
    # 관련 글: 같은 키워드 최신 3편
    rel = [p for p in posts if p['keyword'] == kw and p['slug'] != slug][:3]
    rel_html = ''.join(f'<li><a href="/{p["slug"]}/">{E(p["title"])}</a></li>' for p in rel)
    hub = CFG.get('hubs', {}).get(kw, f'/{kw}/')
    rel_html += f'<li><a href="{hub}">{E(kw)} 안내 페이지</a></li>'
    s = t
    s = re.sub(r'<title>.*?</title>', f'<title>{E(full_title)}</title>', s, count=1, flags=re.S)
    s = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + E(desc, quote=True) + m.group(2), s, count=1)
    s = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + url_raw + m.group(2), s, count=1)
    s = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + url_enc + m.group(2), s, count=1)
    for k in ('og:title', 'twitter:title'):
        s = re.sub(rf'(<meta (?:property|name)="{k}" content=")[^"]*(")', lambda m: m.group(1) + E(full_title, quote=True) + m.group(2), s, count=1)
    for k in ('og:description', 'twitter:description'):
        s = re.sub(rf'(<meta (?:property|name)="{k}" content=")[^"]*(")', lambda m: m.group(1) + E(desc, quote=True) + m.group(2), s, count=1)
    for k in ('og:image', 'twitter:image'):
        s = re.sub(rf'(<meta (?:property|name)="{k}" content=")[^"]*(")', lambda m: m.group(1) + og_img + m.group(2), s, count=1)
    # Article LD
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': title, 'datePublished': date,
          'author': {'@type': 'Organization', 'name': CFG['brand']}, 'publisher': {'@type': 'Organization', 'name': CFG['brand']}, 'about': kw}
    s = re.sub(r'<script type="application/ld\+json">\{[^<]*"@type": ?"Article".*?</script>',
               '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace('</', '<\\/') + '</script>', s, count=1, flags=re.S)
    # 본문
    art = re.search(r'(<article class="post-body">)(.*?)(</article>)', s, re.S)
    inner = (f'\n<h1 class="ph">{E(title)}</h1>\n<div class="pd">{y}년 {mo}월 {d}일 · 댓글 없음 · {E(kw)}</div>\n'
             f'<p class="lead">{E(lead)}</p>\n{body_html(blocks)}\n<p class="tags">{E(tags_html)}</p>\n'
             f'<nav class="relbox"><b>{E(kw)} 관련 글</b><ul>{rel_html}</ul></nav>\n')
    s = s[:art.start(2)] + inner + s[art.end(2):]
    # 템플릿 글에 붙어 있던 추가 정보/퀵메뉴 블록은 제거(빌드 후처리에서 다시 넣음)
    s = re.sub(r'<!-- extra-info:start -->.*?<!-- extra-info:end -->', '', s, flags=re.S)
    s = re.sub(r'<!-- quickmenu:start -->.*?<!-- quickmenu:end -->', '', s, flags=re.S)
    return s, {'slug': slug, 'title': title, 'date': date, 'lead': lead, 'keyword': kw, 'url': url_raw}

def bitem(p):
    y, mo, d = p['date'].split('-')
    return (f'<article class="bitem"><h2><a href="/{p["slug"]}/">{E(p["title"])}</a></h2>'
            f'<div class="bmeta"><time datetime="{p["date"]}">{y}년 {mo}월 {d}일</time><span class="by">작성자: <b>{E(CFG.get("author", CFG["keyword"]))}</b></span></div>'
            f'<p>{E(p["lead"])} <a class="more" href="/{p["slug"]}/">더 읽기</a></p>'
            f'<div class="bcat">카테고리 <span>{E(CFG.get("category", "미분류"))}</span></div></article>')

def rebuild_lists(new=None):
    """blog/index.html + blog/page/N 재구성. 기존 bitem HTML은 그대로 유지, 새 글만 맨 앞에 추가."""
    items = []
    pages = [DIST / 'blog' / 'index.html'] + sorted((DIST / 'blog' / 'page').glob('*/index.html'), key=lambda p: int(p.parent.name))
    for p in pages:
        s = p.read_text(encoding='utf-8')
        items += re.findall(r'<article class="bitem">.*?</article>', s, re.S)
    if new: items.insert(0, bitem(new))
    per = CFG.get('per_page', 10)
    tpl1 = pages[0].read_text(encoding='utf-8'); tplN = pages[1].read_text(encoding='utf-8') if len(pages) > 1 else tpl1
    chunks = [items[i:i + per] for i in range(0, len(items), per)]
    total = len(chunks)
    def pager(cur):
        return '<nav class="pager">' + ''.join(f'<a class="{"on" if n == cur else ""}" href="{"/blog/" if n == 1 else f"/blog/page/{n}/"}">{n}</a>' for n in range(1, total + 1)) + '</nav>'
    for n, chunk in enumerate(chunks, 1):
        tpl = tpl1 if n == 1 else tplN
        s = tpl
        s = re.sub(r'(<div class="blist">).*?(</div>\s*<nav class="pager">.*?</nav>)', lambda m: m.group(1) + '\n' + '\n'.join(chunk) + '\n</div>\n' + pager(n), s, count=1, flags=re.S)
        path = '/blog/' if n == 1 else f'/blog/page/{n}/'
        s = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + origin() + path + m.group(2), s, count=1)
        s = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + origin() + path + m.group(2), s, count=1)
        base = re.sub(r' \(\d+페이지\)', '', re.search(r'<title>(.*?)</title>', tpl1).group(1))
        ttl = base if n == 1 else f'{base} ({n}페이지)'
        s = re.sub(r'<title>.*?</title>', f'<title>{ttl}</title>', s, count=1)
        s = re.sub(r'(<meta (?:property|name)="(?:og|twitter):title" content=")[^"]*(")', lambda m: m.group(1) + ttl + m.group(2), s)
        out = DIST / 'blog' / 'index.html' if n == 1 else DIST / 'blog' / 'page' / str(n) / 'index.html'
        out.parent.mkdir(parents=True, exist_ok=True); out.write_text(s, encoding='utf-8')
    return len(items), total

def update_sitemap(meta):
    p = DIST / 'sitemap.xml'; s = p.read_text(encoding='utf-8')
    if meta['url'] in s: return
    entry = f'  <url><loc>{meta["url"]}</loc><lastmod>{meta["date"]}</lastmod><priority>0.9</priority></url>\n'
    s = s.replace('</urlset>', entry + '</urlset>')
    p.write_text(s, encoding='utf-8')

def update_rss(meta):
    p = DIST / 'rss.xml'; s = p.read_text(encoding='utf-8')
    now = datetime.datetime.now(KST)
    pub = now.strftime('%a, %d %b %Y %H:%M:%S +0900')
    item = (f'  <item>\n    <title>{E(meta["title"])}</title>\n    <link>{meta["url"]}</link>\n    <guid isPermaLink="true">{meta["url"]}</guid>\n'
            f'    <pubDate>{pub}</pubDate>\n    <category>{E(meta["keyword"])}</category>\n    <description>{E(meta["lead"])}</description>\n  </item>\n')
    s = re.sub(r'(<lastBuildDate>)[^<]*(</lastBuildDate>)', lambda m: m.group(1) + pub + m.group(2), s, count=1)
    i = s.find('  <item>'); s = s[:i] + item + s[i:] if i != -1 else s.replace('</channel>', item + '</channel>')
    items = re.findall(r'  <item>.*?</item>\n', s, re.S)
    if len(items) > CFG.get('rss_items', 30):
        for extra in items[CFG.get('rss_items', 30):]: s = s.replace(extra, '', 1)
    p.write_text(s, encoding='utf-8')

def cmd_publish(a):
    ok, slug, fm, blocks = cmd_check(a, quiet=False)
    if not ok: print('검수 FAIL — 발행하지 않음'); sys.exit(3)
    posts = post_index()
    html, meta = render_post(fm, blocks, slug, posts)
    out = DIST / slug / 'index.html'; out.parent.mkdir(parents=True)
    out.write_text(html, encoding='utf-8')
    n, pages = rebuild_lists(meta)
    update_sitemap(meta); update_rss(meta)
    print(f'발행: {meta["url"]} | 목록 {n}편/{pages}페이지 | sitemap·rss 갱신')

def cmd_index(a):
    posts = post_index()
    for p in posts[:a.n]: print(p['date'], p['slug'], '|', p['title'])
    print('총', len(posts), '편')

def main():
    global ROOT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=None)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('index'); s.add_argument('-n', type=int, default=20)
    s = sub.add_parser('publish'); s.add_argument('slug')
    s = sub.add_parser('check'); s.add_argument('slug')
    sub.add_parser('rebuild-lists')
    a = ap.parse_args()
    ROOT = Path(a.root).resolve() if a.root else Path(__file__).resolve().parents[1]
    load()
    if a.cmd == 'index': cmd_index(a)
    elif a.cmd == 'check': cmd_check(a)
    elif a.cmd == 'publish': cmd_publish(a)
    elif a.cmd == 'rebuild-lists': print(rebuild_lists())

if __name__ == '__main__':
    main()
