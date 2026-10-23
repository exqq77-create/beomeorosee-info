# 수정 금지 (beomeorosee.co.kr)
- docs/index.html (홈), docs/about/, docs/contact/, 허브 페이지 docs/대구피부과/, docs/범어동피부과/, docs/수성구피부과/, docs/대구피부과추천/ 등 하이픈 없는 키워드 폴더
- docs/style.css, docs/wp-content/ (이미지), docs/_headers, docs/_redirects, docs/CNAME, 네이버 인증 파일
- 기존 글 페이지 본문(추가 정보·퀵메뉴 블록은 생성기가 관리)

## 홈·공통 헤더/푸터 (2026-10-23 추가)
- 홈(dist/index.html)은 main 브랜치 `content/home.json` → `python3 -I tools/build_home.py .` 로만 생성한다. 발행 작업에서는 홈을 다시 만들지 않는다(수정 금지).
- 글·목록 페이지의 헤더/푸터는 `scripts/build.py`가 `<!-- chrome:start/end -->`, `<!-- chrome-footer:start/end -->` 마커로 매번 교체한다. 발행 후 반드시 `python3 scripts/build.py` 실행.
- `site-chrome.css`(저장소 루트)와 `home-assets/`는 수정 금지.
