# 글 제작·검수 지침 (워드프레스 내보내기형 정적 사이트: 365raeon.co.kr · beomeorosee.co.kr)

이 브랜치(sources)는 배포되지 않는 **참고 원문 보관소**입니다. 자동발행 세션은 main을 복제한 뒤 이 브랜치를 worktree로 꺼내 `sources/`, `catalog.json`, `tools/pick_source.py`를 사용합니다.

```
git -C <repo> fetch --depth 1 origin sources:refs/remotes/origin/sources
git -C <repo> worktree add ../<repo>-sources origin/sources
```

## 사이트 구조 (main)
- 배포 폴더: `content/site.json`의 `dist` (365raeon=public, beomeorosee=docs). 글 주소는 `/<한글 슬러그>/` (예: `/평택치과-구강건조-상담에서-자주-묻는-것/`).
- 새 글: `content/posts/<영문슬러그>.md` 1개 작성 → `python3 -I tools/wp_static_site.py check <영문슬러그>` (PASS 필수) → `python3 -I tools/wp_static_site.py publish <영문슬러그>` → `python3 scripts/build.py`(퀵메뉴·추가정보 후처리) → 커밋·푸시.
  publish가 글 페이지·blog 목록/페이지네이션·sitemap.xml·rss.xml을 갱신합니다. 한글 슬러그는 제목에서 자동 생성됩니다.
- frontmatter: `title`(키워드로 시작, 15~45자), `description`(요약 1~2문장, 40~120자 — 목록·RSS·meta에 쓰임), `date`(YYYY-MM-DD), `keyword`(허브 키워드, 기본값은 site.json의 keyword), `tags`(쉼표 구분, 선택), `og_image`(선택).
- 본문: `## ` 소제목 4~7개(필요하면 `### `), 문단은 빈 줄로 구분. 실질 본문 1,500~2,500자(공백 제외). 이미지·링크·HTML 금지.
- 홈·허브 페이지(`/평택치과/`, `/대구피부과/` 등)·about·contact는 수정하지 않습니다(PROTECTED.md).

## 원문 사용
1. `python3 -I tools/pick_source.py <sources_dir> pick <topic> --n 3`으로 사용 횟수가 적은 원문을 고르고 읽어서 주제가 맞는지 확인합니다. **원문이 없는 주제는 글을 쓰지 않습니다.**
2. 원문에서 가져올 것은 핵심 주제와 확인 가능한 사실뿐입니다. 문장·구조·소제목·도입·결론을 따라가지 않고, 단어 치환·어미 변경·순서 변경으로 끝내지 않습니다.
3. 1인칭 칼럼·후기·상담 사례·사진 지시·메모·원장 이름·다른 지역명은 제거합니다. 다른 업체 원문은 참고하지 않습니다.
4. 글을 만든 뒤 `python3 -I tools/pick_source.py <sources_dir> log <원문id> <슬러그> <날짜> "<메모>"`로 사용 이력을 남기고 sources 브랜치를 커밋·푸시합니다.

## 문체 (기존 글과 동일하게)
- 제목: `<키워드> <소주제>, <질문·확인 기준>` 형식 (예: "평택치과 구강건조, 상담에서 자주 묻는 것"). 같은 키워드 최근 글 제목과 소주제가 겹치지 않게.
- 첫 문단(description)은 "일반적인 안내이며 개인 상태는 진료에서 확인" 취지의 짧은 요약 + 핵심 한 문장.
- 소제목마다 짧은 문단 3~6개, 한 문단은 1~2문장. 환자 눈높이, 단정 없음, 결과 보장·과장·비교우위·가격 단정·이벤트 금지. 마지막 소제목은 "<키워드>에 오시기 전에" 류의 상담 안내로 마무리.
- 사이트별 금지어는 `content/site.json`의 `forbidden`/`forbidden_patterns`에 있으며 check가 FAIL 처리합니다.

## 검수·발행 판정
- `check`가 PASS이고(분량·소제목·금지어·제목 중복·슬러그 중복), 같은 키워드 최근 3편과 의미 중복이 없는지 직접 확인한 글만 발행합니다.
- FAIL이면 고쳐서 다시 검사합니다. 발행량을 채우려고 그대로 공개하지 않습니다.
- 발행 후 `git status`로 변경 범위가 새 글 폴더 + blog/ 목록 + sitemap.xml + rss.xml + content/ 범위인지 확인합니다. 홈 index.html이 바뀌었으면 발행하지 말고 보고합니다.
