#!/usr/bin/env python3
"""keun형 정보 사이트: 홈 ItemList 카드 6장이 가리키는 허브 페이지의 대표 이미지를 카드 사진으로 통일.
og:image(+w/h/alt)·twitter:image, JSON-LD MedicalWebPage.image/primaryImageOfPage, MedicalClinic.image, 본문 hero <img>."""
import json, os, re, sys, html as H
from urllib.parse import unquote

root = sys.argv[1].rstrip('/')
home = open(root + '/index.html', encoding='utf-8').read()
origin = re.search(r'<link rel="canonical" href="(https://[^/"]+)', home).group(1)

# ItemList + card alt from home
il = None
for s in re.findall(r'<script[^>]+ld\+json[^>]*>(.*?)</script>', home, re.S):
    j = json.loads(s); objs = j if isinstance(j, list) else [j] + (j.get('@graph') or [])
    for o in objs:
        if isinstance(o, dict) and o.get('@type') == 'ItemList': il = o
cards = []
for it in il['itemListElement']:
    url = it.get('url') or it['item']['url']; img = it.get('image') or it['item']['image']
    if isinstance(img, dict): img = img['url']
    stem = img.split('/')[-1]
    m = re.search(r'<img[^>]*src="[^"]*' + re.escape(stem) + r'"[^>]*>', home)
    alt = re.search(r'alt="([^"]*)"', m.group(0)).group(1) if m else ''
    cards.append((url, img, alt))

def page_path(url):
    p = unquote(re.sub(r'^https?://[^/]+', '', url)).rstrip('/')
    for c in (root + p + '/index.html', root + p + '.html'):
        if os.path.isfile(c): return c
    return None

changed = []
for url, img, alt in cards:
    f = page_path(url)
    if not f: print('MISSING', url); continue
    h = open(f, encoding='utf-8').read(); o = h
    ealt = H.escape(alt, quote=True)
    try:
        from PIL import Image; W = Image.open(root + unquote(img.replace(origin, ''))).size[0]
    except Exception: W = 860
    # og:image (+ width/height/alt), twitter:image
    h = re.sub(r'<meta property="og:image" content="[^"]*">', f'<meta property="og:image" content="{img}">', h, count=1)
    h = re.sub(r'<meta property="og:image:width" content="[^"]*">', '', h); h = re.sub(r'<meta property="og:image:height" content="[^"]*">', '', h)
    h = re.sub(r'<meta property="og:image:alt" content="[^"]*">', '', h)
    h = h.replace(f'<meta property="og:image" content="{img}">', f'<meta property="og:image" content="{img}"><meta property="og:image:width" content="{W}"><meta property="og:image:height" content="{W}"><meta property="og:image:alt" content="{ealt}">', 1)
    if 'og:image' not in h:
        h = h.replace('<meta property="og:url"', f'<meta property="og:image" content="{img}"><meta property="og:image:width" content="{W}"><meta property="og:image:height" content="{W}"><meta property="og:image:alt" content="{ealt}"><meta property="og:url"', 1)
    if 'twitter:image' in h: h = re.sub(r'<meta name="twitter:image" content="[^"]*">', f'<meta name="twitter:image" content="{img}">', h, count=1)
    else: h = h.replace('<meta name="twitter:card" content="summary_large_image">', f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{img}">', 1)
    # JSON-LD
    def fix_ld(m):
        try: j = json.loads(m.group(1))
        except Exception: return m.group(0)
        objs = j if isinstance(j, list) else [j] + (j.get('@graph') or [])
        hit = False
        for ob in objs:
            if not isinstance(ob, dict): continue
            t = ob.get('@type')
            if t in ('MedicalClinic', 'Dentist', 'MedicalBusiness'):
                ob['image'] = img; hit = True
            if t in ('MedicalWebPage', 'WebPage', 'CollectionPage'):
                ob['image'] = img
                ob['primaryImageOfPage'] = {'@type': 'ImageObject', 'url': img, 'caption': alt}
                hit = True
        if hit and not any(isinstance(ob, dict) and ob.get('@type') in ('MedicalWebPage', 'WebPage', 'CollectionPage') for ob in objs) and isinstance(j, dict) and isinstance(j.get('@graph'), list):
            t = re.search(r'<title>(.*?)</title>', h, re.S); t = H.unescape(t.group(1).strip()) if t else ''
            j['@graph'].append({'@type': 'WebPage', '@id': url + '#webpage', 'url': url, 'name': t, 'inLanguage': 'ko-KR',
                                'isPartOf': {'@id': origin + '/#website'}, 'about': {'@id': origin + '/#clinic'}, 'image': img,
                                'primaryImageOfPage': {'@type': 'ImageObject', 'url': img, 'caption': alt}})
        if not hit: return m.group(0)
        return m.group(0).replace(m.group(1), json.dumps(j, ensure_ascii=False, separators=(',', ':')))
    before = h
    h = re.sub(r'<script type="application/ld\+json">(.*?)</script>', fix_ld, h, flags=re.S)
    if '"primaryImageOfPage"' not in h:  # 구조화 데이터가 없거나 손대지 못한 페이지: WebPage 블록 추가
        t = re.search(r'<title>(.*?)</title>', h, re.S); t = H.unescape(t.group(1).strip()) if t else ''
        wp = {'@context': 'https://schema.org', '@type': 'WebPage', '@id': url + '#webpage', 'url': url, 'name': t, 'inLanguage': 'ko-KR',
              'isPartOf': {'@id': origin + '/#website'}, 'about': {'@id': origin + '/#clinic'}, 'image': img,
              'primaryImageOfPage': {'@type': 'ImageObject', 'url': img, 'caption': alt}}
        h = h.replace('</head>', '<script type="application/ld+json">' + json.dumps(wp, ensure_ascii=False, separators=(',', ':')) + '</script></head>', 1)
    # body hero: first <img> after <h1> that is not the logo
    def fix_hero(m):
        tag = m.group(0)
        if 'logo' in tag: return tag
        cls = re.search(r'class="([^"]*)"', tag)
        cls = f' class="{cls.group(1)}"' if cls else ''
        return f'<img{cls} src="{img.replace(origin, "")}" width="{W}" height="{W}" alt="{ealt}" loading="eager" decoding="async" fetchpriority="high">'
    h1 = h.find('<h1'); nxt = min([x for x in (h.find(t, h1) for t in ('<h2', '<article', '<li', '<ul ')) if x > -1] or [-1])
    seg = h[h1:nxt] if nxt > h1 > -1 else ''
    if seg:
        new_seg = re.sub(r'<img[^>]*>', fix_hero, seg, count=1)
        if new_seg == seg:  # no hero image → insert after lead paragraph or h1
            ins = f'<figure class="mt-2 hub-hero" style="margin:0 0 20px"><img class="wide" src="{img.replace(origin, "")}" width="{W}" height="{W}" alt="{ealt}" loading="eager" decoding="async" fetchpriority="high" style="max-width:100%;height:auto;border-radius:12px"></figure>'
            lp = seg.find('</p>', seg.find('class="lead"')) if 'class="lead"' in seg else -1
            new_seg = seg[:lp + 4] + ins + seg[lp + 4:] if lp > -1 else re.sub(r'(</h1>)', r'\1' + ins, seg, count=1)
        h = h[:h1] + new_seg + h[nxt:]
    if h != o:
        open(f, 'w', encoding='utf-8').write(h); changed.append(f.replace(root + '/', ''))
print(os.path.basename(root), 'changed', len(changed), changed)
