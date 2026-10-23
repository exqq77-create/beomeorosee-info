#!/usr/bin/env python3
"""새론이치과 홈 구조로 홈(index.html)을 생성한다 (content/home.json + content/site.json).
구성: 유틸리티 바 → 헤더(키워드·로고·공식 링크) → 사진 카드 6개(캐러셀) → 소개(hero) → 진료 전 살펴볼 네 가지 →
진료 항목 자세히 보기 → 치료·시술 전후 일정 → 상담 팁·질문(FAQ) → 미리 알려주면 좋은 정보 → 오시는 길 → 병원 안내 →
의료정보 안내 → 전체 글 링크 → 푸터 → 모바일 전화 바. JSON-LD: WebSite·WebPage·MedicalClinic/Dentist·ItemList·FAQPage.
사용: python3 build_home.py <repo_root> [--assets <home-assets 폴더>]
"""
import json, re, sys, html, datetime
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance

E = lambda s: html.escape(str(s), quote=True)


def card_images(root, dist, cards, cards_adjust=None):
    """원본 사진 → 정사각 1024/480 jpg + webp (dist/images/home/<key>-photo[-small].{jpg,webp})."""
    out_dir = dist / 'images' / 'home'; out_dir.mkdir(parents=True, exist_ok=True)
    for c in cards:
        src = dist / c['photo'].lstrip('/')
        im = ImageOps.exif_transpose(Image.open(src)).convert('RGB'); w, h = im.size
        adj = c.get('adjust') or (cards_adjust if isinstance(cards_adjust, dict) else {})
        if adj.get('brightness'): im = ImageEnhance.Brightness(im).enhance(adj['brightness'])
        if adj.get('contrast'): im = ImageEnhance.Contrast(im).enhance(adj['contrast'])
        fx, fy = c.get('focus', [0.5, 0.5])
        m = min(w, h)
        left = int(max(0, min(w - m, fx * w - m / 2))); top = int(max(0, min(h - m, fy * h - m / 2)))
        sq = im.crop((left, top, left + m, top + m))
        for size, suffix in ((1024, ''), (480, '-small')):
            r = sq.resize((size, size), Image.LANCZOS)
            r.save(out_dir / f"{c['key']}-photo{suffix}.jpg", 'JPEG', quality=86, optimize=True, progressive=True)
            r.save(out_dir / f"{c['key']}-photo{suffix}.webp", 'WEBP', quality=82)
        c['img'] = f"/images/home/{c['key']}-photo"


def render(root):
    site = json.loads((root / 'content' / 'site.json').read_text(encoding='utf-8'))
    H = json.loads((root / 'content' / 'home.json').read_text(encoding='utf-8'))
    dist = root / site['dist']; O = site['origin'].rstrip('/')
    assets = Path(H.get('assets_dir') or (Path(__file__).resolve().parent / 'home-assets'))
    old = (dist / 'index.html').read_text(encoding='utf-8') if (dist / 'index.html').exists() else ''
    naver = re.search(r'<meta name="naver-site-verification"[^>]*>', old)
    icons = re.findall(r'<link rel="(?:icon|apple-touch-icon)"[^>]*>', old)
    card_images(root, dist, H['cards'], H.get('cards_adjust'))
    kw, brand = H['keyword'], H['brand']
    theme = ''.join(f'{k}:{v};' for k, v in H.get('theme', {}).items())
    css = ''.join('<style>' + (assets / f).read_text(encoding='utf-8') + '</style>' for f in ('styles.css', 'extra.css', 'home-layout.css', 'homepage-original.css', 'homepage-details.css'))
    css += '<style>.brand img.brand-symbol{width:44px;height:44px;object-fit:contain}.brand .brand-name{font-size:19px;font-weight:700;color:var(--navy);white-space:nowrap;margin-left:-10px}@media(max-width:800px){.brand .brand-name{font-size:16px}.brand img.brand-symbol{width:36px;height:36px}}</style>'
    css += f'<style>:root{{{theme}}} .source-homeguide{{--guide-accent:{H["theme"].get("--blue", "#0074aa")}}}</style>' if theme else ''
    js = (assets / 'carousel.js').read_text(encoding='utf-8')
    first = H['cards'][0]['img']
    # ---- JSON-LD ----
    clinic_type = H.get('clinic_type', 'MedicalClinic')
    ld_site = {'@context': 'https://schema.org', '@type': 'WebSite', '@id': O + '/#website', 'name': kw, 'alternateName': brand, 'url': O + '/', 'inLanguage': 'ko-KR', 'publisher': {'@id': O + '/#clinic'}}
    ld_clinic = {'@context': 'https://schema.org', '@type': clinic_type, '@id': O + '/#clinic', 'name': brand, 'url': O + '/', 'telephone': H['tel_intl'], 'image': O + first + '.jpg', 'logo': O + H['logo']['src'],
                 'address': H['address_schema'], 'sameAs': H['same_as'], 'openingHoursSpecification': H['hours_schema']}
    ld_page = {'@context': 'https://schema.org', '@type': 'WebPage', '@id': O + '/#webpage', 'url': O + '/', 'name': H['title'], 'description': H['description'], 'inLanguage': 'ko-KR',
               'isPartOf': {'@id': O + '/#website'}, 'about': {'@id': O + '/#clinic'},
               'primaryImageOfPage': {'@type': 'ImageObject', 'url': O + first + '.jpg', 'width': 1024, 'height': 1024, 'caption': H['cards'][0]['alt']}}
    ld_list = {'@context': 'https://schema.org', '@type': 'ItemList', 'name': f'{kw} {brand} 주요 안내', 'numberOfItems': len(H['cards']), 'itemListOrder': 'https://schema.org/ItemListOrderAscending',
               'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': c['title'], 'url': O + c['href'], 'image': O + c['img'] + '.jpg'} for i, c in enumerate(H['cards'])]}
    ld_faq = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q['q'], 'acceptedAnswer': {'@type': 'Answer', 'text': q['a']}} for q in H['questions']]}
    lds = ''.join('<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False).replace('</', '<\\/') + '</script>' for d in (ld_site, ld_page, ld_clinic, ld_list, ld_faq))
    # ---- head ----
    head = (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'{naver.group(0) if naver else ""}<title>{E(H["title"])}</title><meta name="description" content="{E(H["description"])}">'
            f'<link data-speed-preload="first-image" rel="preload" as="image" href="{first}.jpg" fetchpriority="high" imagesrcset="{first}-small.jpg 480w, {first}.jpg 1024w" imagesizes="(max-width:800px) 77vw, 380px">'
            f'<link rel="canonical" href="{O}/">{"".join(icons)}<link rel="alternate" type="application/rss+xml" title="{E(brand)} 새 글" href="{O}/rss.xml">'
            f'<meta name="robots" content="index,follow,max-image-preview:large"><meta property="og:type" content="website"><meta property="og:locale" content="ko_KR"><meta property="og:site_name" content="{E(brand)}">'
            f'<meta property="og:title" content="{E(H["title"])}"><meta property="og:description" content="{E(H["description"])}"><meta property="og:url" content="{O}/">'
            f'<meta property="og:image" content="{O}{first}.jpg"><meta property="og:image:width" content="1024"><meta property="og:image:height" content="1024"><meta property="og:image:alt" content="{E(H["cards"][0]["alt"])}">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(H["title"])}"><meta name="twitter:description" content="{E(H["description"])}"><meta name="twitter:image" content="{O}{first}.jpg">'
            f'{css}{lds}</head>')
    # ---- body ----
    logo = H['logo']
    if logo.get('text'):  # 정사각/세로 로고: 심볼 + 텍스트
        logo_html = (f'<img class="brand-symbol" src="{logo["src"]}" width="{logo["width"]}" height="{logo["height"]}" alt="">'
                     f'<span class="brand-name">{E(logo["text"])}</span>')
    else:
        logo_html = f'<img src="{logo["src"]}" width="{logo["width"]}" height="{logo["height"]}" alt="{E(brand)}">'
    header = (f'<body class="home-layout"><a class="skip" href="#content">본문 바로가기</a>'
              f'<div class="utility"><div class="wrap"><span>{E(H["utility"])}</span><a href="tel:{H["tel_href"]}">{E(H["tel"])}</a></div></div>'
              f'<header class="header"><div class="wrap"><a class="brand" href="/" aria-label="{E(kw)} {E(brand)} 홈"><span class="site-keyword">{E(kw)}</span><span class="bar" aria-hidden="true"></span>{logo_html}</a>'
              f'<nav class="homepage-keyword" aria-label="공식 병원 안내"><a href="{H["official"]}" target="_blank" rel="noopener noreferrer">{E(kw)}</a></nav></div></header><main id="content">')
    cards = ''
    for i, c in enumerate(H['cards'], 1):
        img = c['img']
        cards += (f'<article class="card" data-carousel-card><a href="{c["href"]}"><div class="card-image"><picture>'
                  f'<source type="image/webp" srcset="{img}-small.webp 480w, {img}.webp 1024w" sizes="(max-width:800px) 77vw, 380px">'
                  f'<img src="{img}.jpg" srcset="{img}-small.jpg 480w, {img}.jpg 1024w" sizes="(max-width:800px) 77vw, 380px" alt="{E(c["alt"])}" width="1024" height="1024" loading="{"eager" if i <= 3 else "lazy"}" decoding="async"{" fetchpriority=\"high\"" if i == 1 else ""}>'
                  f'</picture></div><p class="kicker">{i:02d} / {E(c["kicker"])}</p><h2>{E(c["title"])}</h2><p>{E(c["desc"])}</p><span class="readmore">자세히 보기 →</span></a></article>')
    carousel = (f'<section class="wrap homepage-carousel" aria-label="{E(kw)} 주요 안내"><div class="heading"><h2>{E(brand)} 주요 안내</h2><div class="arrows">'
                f'<span class="carousel-status" aria-live="polite" aria-atomic="true">1 / {len(H["cards"])}</span>'
                f'<button type="button" data-carousel-direction="-1" aria-controls="main-carousel" aria-label="이전 안내 보기" disabled>‹</button>'
                f'<button type="button" data-carousel-direction="1" aria-controls="main-carousel" aria-label="다음 안내 보기">›</button></div></div>'
                f'<div class="carousel" id="main-carousel" tabindex="0" role="region" aria-label="{E(brand)} 주요 안내 {len(H["cards"])}개">{cards}</div></section>')
    hero = H['hero']
    guide = (f'<article class="source-homeguide" id="treatments" data-original-revision="{H.get('revision', 'home-1')}"><header class="original-hero"><p class="original-kicker">{E(brand)}</p>'
             f'<h1>{E(hero["title"])}</h1><p class="original-subtitle">{E(hero["subtitle"])}</p>' + ''.join(f'<p>{E(p)}</p>' for p in hero['paras']) + '</header>')
    guide += ('<section class="original-section" id="guide-checkpoints"><p class="original-kicker">CHECKPOINT 01–04</p><h2>진료 전 살펴볼 네 가지</h2><div class="original-checks">' +
              ''.join(f'<div class="original-check"><span class="original-count">{i:02d}</span><h3>{i:02d} · {E(c["title"])}</h3><p>{E(c["text"])}</p></div>' for i, c in enumerate(H['checkpoints'], 1)) + '</div></section>')
    guide += ('<section class="original-section" id="guide-treatments"><p class="original-kicker">TREATMENT GUIDE</p><h2>진료 항목 자세히 보기</h2><div class="original-treatments">' +
              ''.join(f'<div class="original-treatment"><span>{i:02d}</span><div><h3>{E(t["title"])}</h3><p>{E(t["text"])}</p></div></div>' for i, t in enumerate(H['treatments'], 1)) + '</div></section>')
    guide += ('<section class="original-section" id="guide-stages"><p class="original-kicker">BEFORE &amp; AFTER</p><h2>치료·시술 전후 일정 안내</h2><div class="original-stages" role="list">' +
              ''.join(f'<div class="original-stage" role="listitem"><div><span>{E(s["phase"])}</span><h3>{i:02d} · {E(s["title"])}</h3></div><p>{E(s["text"])}</p></div>' for i, s in enumerate(H['stages'], 1)) +
              f'</div><p class="original-note">{E(H["stage_note"])}</p></section>')
    guide += ('<section class="original-section" id="guide-consultation"><p class="original-kicker">CONSULTATION</p><h2>상담을 준비하는 팁과 질문</h2><div class="original-tips"><ul>' +
              ''.join(f'<li>{E(t)}</li>' for t in H['tips']) + '</ul></div><div class="original-questions">' +
              ''.join(f'<details><summary>{E(q["q"])}</summary><p>{E(q["a"])}</p></details>' for q in H['questions']) + '</div></section>')
    guide += ('<section class="original-section" id="guide-patient-info"><p class="original-kicker">YOUR INFORMATION</p><h2>환자가 미리 알려주면 좋은 정보</h2><ul>' +
              ''.join(f'<li>{E(t)}</li>' for t in H['patient_info']) + '</ul></section>')
    d = H['directions']
    guide += (f'<section class="original-section" id="guide-directions"><p class="original-kicker">LOCATION</p><h2>{E(brand)} 오시는 길</h2><p class="original-address">{E(H["address_short"])}</p>' +
              ''.join(f'<p>{E(p)}</p>' for p in d['paras']) +
              f'<div class="original-actions"><a href="tel:{H["tel_href"]}"><span>전화 문의</span><strong>{E(H["tel"])}</strong></a>'
              f'<a href="{H["map"]}" target="_blank" rel="noopener noreferrer"><span>네이버 플레이스</span><strong>위치·예약 정보 ↗</strong></a>'
              f'<a href="{H["official"]}" target="_blank" rel="noopener noreferrer"><span>공식 홈페이지</span><strong>병원 안내 바로가기 ↗</strong></a></div></section>')
    c = H['clinic']
    guide += (f'<section class="original-section" id="guide-clinic"><p class="original-kicker">CLINIC INFORMATION</p><h2>병원 안내</h2><p>{E(c["intro"])}</p><dl class="original-facts">' +
              ''.join(f'<div><dt>{E(k)}</dt><dd>{E(v)}</dd></div>' for k, v in c['facts']) + '</dl>' +
              ('<details class="original-references"><summary>안내에 참고한 공식 자료</summary><ul>' + ''.join(f'<li><a href="{r["url"]}" target="_blank" rel="noopener noreferrer">{E(r["title"])}</a></li>' for r in H.get('references', [])) + '</ul></details>' if H.get('references') else '') +
              '</section>')
    guide += f'<aside class="original-medical"><h2>의료정보 안내</h2><p>{E(H["medical_note"])}</p></aside></article>'
    archive = '<nav class="home-archive-link" aria-label="건강정보 전체 글" style="max-width:900px;margin:0 auto 48px;padding:0 24px"><a href="/blog/">건강정보 전체 글 →</a></nav></main>'
    f = H['footer']
    footer = (f'<footer class="footer"><div class="wrap"><div class="footer-top"><div><h2>{E(brand)}</h2>' + ''.join(f'<p>{E(p)}</p>' for p in f['lines']) +
              f'<p>대표전화 <a href="tel:{H["tel_href"]}">{E(H["tel"])}</a></p></div><div class="footer-links">' +
              ''.join(f'<a href="{l["url"]}" target="_blank" rel="noopener">{E(l["text"])}</a>' for l in f['links']) +
              f'</div></div><div class="disclaimer">{E(H["disclaimer"])}</div></div></footer>'
              f'<div class="mobile-call"><a href="tel:{H["tel_href"]}">전화 문의</a><a href="{H["map"]}" target="_blank" rel="noopener">네이버 예약</a></div>'
              f'<script>{js}</script></body></html>')
    out = head + header + carousel + guide + archive + footer
    (dist / 'index.html').write_text(out, encoding='utf-8')
    print(f'home written: {dist / "index.html"} ({len(out)} bytes), cards={len(H["cards"])}, faq={len(H["questions"])}')


if __name__ == '__main__':
    render(Path(sys.argv[1]).resolve())
