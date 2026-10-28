# 팍스 로마나 데일리

AS 로마만 다루는 한국어 번역 팬 사이트입니다. 뉴스보다 **전술 분석·선수/팀 칼럼·역사**를 우선하고, 최신 영상도 함께 모읍니다.

- 로그인/비밀번호 없음. 정적 HTML 한 장이라 GitHub Pages나 Cloudflare Pages에 그대로 올라갑니다.
- 하루 **번역 7개** = 장문 기사 3 + 칼럼 4 (기사:칼럼 ≈ 2:3) + **원본 영상 4개**.
- 기사는 경기 실황·득점 장면이 살아 있는 장문을 우선하고, 칼럼은 전술·선수/팀·역사 글을 우선합니다.
- 로마 관련 글만 수집합니다.
- 과거 팀 역사·전설 칼럼은 `역사` 태그와 별도 섹션으로 보여줍니다.
- 영상은 번역하지 않고 최신순으로 원본만 노출합니다.
- 배포·운영 방법은 [DEPLOY.md](DEPLOY.md)에 정리했습니다.


---

## 1. 구조

```text
seriea-feed/
├─ config.py                 # 팀·소스·칼럼·YouTube 채널·쿼터·LLM 설정
├─ fetcher.py                # 원문 수집 (뉴스 RSS / 칼럼 블로그 / Reddit / YouTube)
├─ processor.py              # 팀·경기 분류, 중복 제거, 요약·번역, 캐시
├─ fixtures.py               # TheSportsDB로 최근 경기 결과 → matches.json
├─ build_site.py             # data/articles.json → site/index.html
├─ pipeline.py               # 경기 갱신 → 수집 → 번역 → 병합 → 빌드
├─ requirements.txt
├─ tests/
│  ├─ test_fixtures.py       # 경기 파싱/병합 모의 테스트
│  └─ test_reddit.py         # Reddit OAuth/댓글 파싱 모의 테스트
├─ templates/
│  └─ index.html             # 정적 프론트 (CSS/JS 포함, 빌드 시 데이터 주입)
├─ data/
│  ├─ matches.json           # 최근 경기 목록 (우선 노출·중복 판단에 사용)
│  ├─ matches.sample.json    # 형식 예시
│  ├─ raw.json               # 생성물: 이번 수집 원문
│  ├─ articles.json          # 생성물: 번역·분류 결과
│  ├─ cache.json             # 생성물: 번역 캐시
│  └─ youtube_channels.json  # 생성물: 핸들 → 채널 ID 캐시
├─ site/                     # 생성물: GitHub Pages에 배포되는 정적 사이트
│  ├─ index.html
│  └─ data/feed.json         # 다른 클라이언트가 쓸 수 있는 JSON 피드
└─ .github/workflows/feed.yml
```

프론트는 `site/index.html` 하나에 CSS/JS/데이터가 모두 들어갑니다. 서버·DB·프레임워크 없음.

---

## 2. 로컬 실행

Python 3.11+ 기준입니다.

```bash
cd seriea-feed
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# .env.example을 .env로 복사하고 키 입력
copy .env.example .env        # Windows
cp .env.example .env          # macOS/Linux

# 또는 환경변수로 직접 지정
set OPENCODE_API_KEY=oc_sk_...        # Windows PowerShell: $env:OPENCODE_API_KEY="oc_sk_..."
export OPENCODE_API_KEY=oc_sk_...     # macOS/Linux

python pipeline.py                 # 전체 수집 + 번역 + 빌드
python -m http.server 8000 --directory site
# http://localhost:8000
```

처음 비용을 아끼고 싶으면:

```bash
python pipeline.py --fresh --quota news=2,column=3,video=0 --skip-fixtures
# → 번역 5개만 처리하고 사이트를 미리보기 상태로 빌드
```

`data/raw.json`만 만들고 번역은 나중에 하려면 `python fetcher.py`를 따로 실행해도 됩니다.

Reddit OAuth 로직은 실제 API 없이 검증할 수 있습니다.

```bash
python -m unittest discover -s tests -v
```

---

## 3. OpenCode API 연결

기본값은 **OpenCode Go** 구독용 OpenAI 호환 엔드포인트입니다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `OPENCODE_API_KEY` | (없음) | OpenCode Console에서 발급한 키 |
| `OPENCODE_BASE_URL` | `https://opencode.ai/inference/go/openai/v1` | Go 구독 엔드포인트 |
| `OPENCODE_MODEL` | `deepseek-v4.1-flash` | 번역 모델 ID |
| `OPENCODE_REASONING_EFFORT` | `none` | 추론 토큰 사용량. `none`이면 번역 토큰을 온전히 쓴다 |
| `OPENCODE_SESSION` | `seriea-feed` | `x-opencode-session` 헤더 값 |

Console(종량제)을 쓰려면:

```bash
OPENCODE_BASE_URL=https://opencode.ai/inference/openai/v1
OPENCODE_MODEL=deepseek-v4.1-flash
```

- 번역은 `chat/completions` 한 번으로 제목·요약·태그를 만들고, 본문은 3,500자 단위로 나눠 이어서 번역합니다.
- 결과는 `data/cache.json`에 기사 해시별로 저장됩니다. 같은 글은 다시 실행해도 과금되지 않습니다.
- 모델을 바꾸거나 프롬프트를 고치면 `config.PROMPT_VERSION`을 올리세요. 전체 재번역됩니다.

### 번역 프롬프트에 들어간 규칙

- 원문에 없는 내용 추가 금지, 광고·구독 유도 제거.
- 선수·감독 이름은 한국 통용 표기, 팀명은 한국어.
- 본문은 **원문 분량의 약 80%**, 문단 구조 유지, 수치·발언·전술 설명은 누락 금지.
- 인터뷰: 따옴표 안의 구어체, "~라고 말했다" 반복 금지, 말투·감탄 유지.
- 레딧: 제목/본문/댓글 개수·순서 유지, 밈·비꼼·욕설 강도 유지.

### 비용 감각 (2026-10-27 측정)

- 7개(장문 기사 3 + 칼럼 4): API 정가 **$0.008 내외**, Go 한도 차감 **$0.006 내외**
- 하루 7개 기준 월 **$0.2~0.3**, Go $80 한도의 1% 미만
- 피크/오프피크에 따라 Go 차감액이 달라집니다.
- 구글 번역 초안 → API 정리(하이브리드)는 API 비용이 약 11%만 줄어 복잡도 대비 이득이 작습니다. 공식 Google Cloud Translation을 쓰면 오히려 훨씬 비쌉니다.

---

## 4. 동작 규칙

### 경기 직후 우선 노출

`data/matches.json`이 최근 경기로 채워져 있으면:

- 경기 종료 후 `MATCH_PRIORITY_HOURS`(기본 24시간) 안에 두 팀이 모두 언급된 글이 `경기 직후` 섹션 최상단으로 갑니다.
- 그 경기에 나온 두 팀의 **다른 기사**도 가산점을 받아 위로 올라옵니다(경기 자체 기사보다는 아래).
- 같은 경기 기사는 `match_key = 날짜:팀쌍`으로 묶여 **보도/분석 1개 + 인터뷰 1개**만 남습니다.
  - 레딧 반응과 영상은 성격이 달라 중복 제거 대상에서 제외합니다.
  - 남길 글은 `번역 완료 > 본문 길이 > 소스 가중치` 순으로 고릅니다.
- `matches.json`이 비어 있어도 제목에 `2-1` 같은 스코어가 있으면 같은 경기로 추정합니다.

형식:

```json
[
  {
    "home": "atalanta",
    "away": "frosinone",
    "score": "4-4",
    "finished_at": "2026-10-25T17:00:00+01:00",
    "competition": "Serie A"
  }
]
```

`home`/`away`는 `config.py`의 `TEAMS[].id`입니다. 이 파일은 `fixtures.py`가 TheSportsDB에서 최근 라운드 결과를 받아 자동으로 갱신합니다.

### 경기 결과 자동 갱신 (TheSportsDB)

`pipeline.py`를 실행하면 수집 전에 `fixtures.update_matches()`가 자동으로 돕니다.

```bash
python fixtures.py --dry-run   # 파일 쓰지 않고 결과 미리보기
python fixtures.py             # matches.json 갱신
python pipeline.py             # 갱신 + 수집 + 번역 + 빌드
python pipeline.py --skip-fixtures  # 경기 갱신만 건너뛰기
```

동작:

1. `eventsnextleague.php`로 다음 경기의 라운드를 확인 (없으면 방금 끝난 경기/기존 파일의 최대 라운드)
2. 기준 라운드 포함 **최근 3개 라운드**를 `eventsround.php`로 조회
3. 종료된 경기만 골라 `home`, `away`, `score`, `finished_at`, `round` 저장
4. 기존 `matches.json`과 병합하고 14일 지난 경기는 제거 (최대 60경기)
5. API/응답 실패 시 **기존 matches.json을 그대로 유지**

- 시즌은 날짜로 자동 계산합니다(7월 이후 시작 연도). `FIXTURE_SEASON=2026-2027`로 고정할 수 있습니다.
- 무료 test key `123`을 기본값으로 씁니다. 운영에서는 `THESPORTSDB_API_KEY`를 본인 키로 바꾸는 걸 권장합니다.
- TheSportsDB 표기(`AC Milan`, `Inter Milan`)는 내부 팀 ID로 자동 변환합니다.
- 종료 시각은 킥오프 + 2시간으로 추정합니다. 우선 노출 판단에는 충분하고, 정확한 기록 통계에는 쓰지 않습니다.
- 경기 데이터 출처 표기는 사이트 하단에 넣어두었습니다.

### 중복 제목 제거

경기 매칭이 안 된 글도 제목 토큰 유사도(0.55 이상) 또는 문자열 유사도(0.82 이상)가 높으면 하나만 남깁니다. 추가로 제목/리드에 두 팀만 또렷하게 나오면 `날짜:팀쌍`으로 묶어 같은 경기 보도로 취급합니다. 정확한 판단은 `matches.json`이 있을 때 가장 잘 동작합니다.

### 팀 분류

`config.py`의 팀 이름·별칭을 제목+본문에서 찾습니다. `2026-27` 시즌 20개 팀이 들어 있고, 승격/강등이 바뀌면 이 목록만 고치면 됩니다. 애매한 별명(`nerazzurri`, `rossoblu` 등)은 오분류를 막기 위해 넣지 않았습니다.

### 영상

- 채널 페이지에서 최신 영상을 최대 24개 수집하고, **하루 4개만 원본 그대로** 노출합니다.
- **여자축구(Women/Femminile) 영상은 제외**하고 남자축구 영상만 사용합니다.
- 영상은 번역·요약하지 않습니다. 제목과 썸네일만 사용합니다.
- `YOUTUBE_CHANNELS`의 핸들을 사용합니다. RSS가 실패하면 채널 HTML을 파싱하고, 그것도 실패하면 RSS로 폴백합니다.
- 채널당 최근 6개, 72시간 이내 영상만 사용합니다.
- 팀 채널을 추가하려면 `config.py`에 `{"team": "bologna", "handle": "채널핸들", "label": "Bologna"}`를 넣으면 됩니다.

### 하루 번역 쿼터

`config.DAILY_QUOTAS`가 하루 목표입니다.

```python
{"news": 3, "column": 4, "video": 4}
```

- GitHub Actions는 **매일 오전 1회**(07:00 KST) 실행됩니다.
- 회차당 **기사 3 + 칼럼 4 = 번역 7개**, 영상은 원본 4개입니다.
- 역사 칼럼은 하루 1개까지 칼럼 4개 안에서 우선 확보합니다.
- `팬 칼럼` 태그: Chiesa di Totti, ForzaRoma, Romanews, AS ROMA電子報告 등 팬/현지 시선 글.
- 한 번에 하루치를 처리하려면:

```bash
python pipeline.py --full-day
```

- 쿼터를 직접 지정하려면:

```bash
python pipeline.py --quota news=3,column=4,video=6
```

- `--fresh`는 기존 `articles.json`을 무시하고 이번 선택분만 사이트에 올립니다. 미리보기/초기화용.
- 실패한 번역을 이전 글에서 다시 시도하려면 `--retranslate`를 추가합니다. 기본은 꺼져 있어 쿼터를 넘지 않습니다.
- 칼럼은 `MAX_COLUMN_BODY_CHARS`(12,000자)를 넘는 장문은 제외해 비용을 통제합니다.

---

## 5. 소스별 현재 상태 (중요)

| 소스 | 방식 | 실제 확인한 것 |
|---|---|---|
| Gazzetta dello Sport | RSS | 피드가 죽어 있어 현재 0개입니다. 살아나면 로마 URL만 사용합니다. |
| Corriere dello Sport | RSS | 로마 팀 페이지(`/roma/`)만 수집하고 본문을 스크래핑합니다. |
| Tuttosport | RSS | 위와 동일. 로마 기사만 사용합니다. |
| ForzaRoma | RSS | 로마 팀 전문 매체. 본문 전체 제공. 뉴스와 분석/칼럼을 함께 사용합니다. |
| Romanews | RSS | 로마 팀 매체. 요약이 짧아 기사 페이지를 일부 스크래핑합니다. |
| RomaPress | RSS | 미국/영어권 로마 전문 매체. 로마 뉴스·인터뷰·프리뷰. 본문 전체 제공. |
| Chiesa di Totti | RSS | 미국 SB Nation의 로마 팬 블로그. `Sinners & Saints` 등 팬 시선 경기 칼럼이 좋습니다. |
| Il Messaggero | RSS | 로마 지역지 스포츠 섹션. 로마 관련 기사만 사용합니다. |
| The Guardian / CBS Sports | RSS | 유럽·미국 축구 매체. 로마 관련 장문만 골라 사용합니다. |
| Sportellate | RSS + 로마/역사 태그 | `Considerazioni Sparse` 전술 분석, 팀 태그, 역사 칼럼. 본문 전체 제공. |
| Ultimo Uomo | RSS | `Calcio` 장문 분석. 로마가 언급된 글만 선택됩니다. |
| Football Italia | RSS | 로마 관련 기사. 칼럼성 글만 칼럼으로 분류합니다. |
| フットボールゾーン / フットボールチャンネル | RSS | 일본어 축구 매체. 현재 피드에서 로마 기사는 드물어 보조 소스로만 사용합니다. |
| AS ROMA電子報告 | RSS | 일본 로마 팬 블로그. 로마 관련 글을 꾸준히 올립니다. |
| The Gentleman Ultra | RSS | 이탈리아 축구 역사·문화 장문. 로마 역사 글이 있을 때 보강합니다. |
| 역사 아카이브 | 큐레이션 URL | 로마 구단 역사·1980~90년대 장문 칼럼을 한 번 번역해 `역사` 섹션에 계속 보여줍니다. |
| r/seriea | OAuth API (없으면 RSS) | 팬 반응/댓글은 수집하지 않습니다. **700자 이상 장문 분석 글만** 칼럼 후보로 가져옵니다. |
| YouTube | 채널 페이지 스크래핑 (RSS 폴백) | Serie A·AS Roma 채널의 일반 영상과 쇼츠를 최신순으로 모아 하루 4개만 원본 노출합니다. 여자축구는 제외합니다. **영상은 번역하지 않습니다.** |

### RSS 소스 추가/교체

`config.py`의 `RSS_SOURCES`에 피드와 URL 필터를 넣으면 됩니다.

```python
{
    "key": "corrieredellosport",
    "feeds": ["https://www.corrieredellosport.it/rss/calcio"],
    "max_items": 10,
    "page_budget": 10,                  # 본문 스크래핑 최대 횟수
    "url_include": ["/roma/"],  # 이 조각이 URL에 있어야 수집
}
```

새 매체를 넣을 때는 `SOURCES`에 라벨/색/가중치도 같이 추가하세요. 본문이 RSS에 없으면 `page_budget`만큼 기사 페이지를 읽어 보강합니다.

### 레딧 칼럼 가져오기

Reddit은 팬 반응/댓글용이 아니라 **장문 분석 글 전용**으로 씁니다.

1. https://www.reddit.com/prefs/apps → **create another app**
2. 이름 입력, 종류는 **script**, redirect uri는 `http://localhost:8080` 입력
3. 생성 후 앱 이름 아래의 **client id**와 `secret` 복사
4. `.env`에 입력

```bash
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
# Reddit이 요구하는 고유 UA. 본인 닉네임을 넣는 게 좋습니다.
REDDIT_USER_AGENT=web:seriea-feed:0.2 (by /u/your_reddit_name)
```

5. 확인

```bash
python fetcher.py
# INFO Reddit OAuth 토큰 발급 완료
# INFO Reddit OAuth: 글 12개 / 긴 글 3개
# INFO Reddit 3개 수집 (OAuth + long-form posts)
```

동작 방식:

- r/seriea **hot 30개** 중 최근 72시간·스티키/NSFW 제외
- `selftext`가 **700자 이상**인 장문 글만 사용 (링크 글·단문·밈 글 제외)
- 댓글은 요청하지 않음 (`REDDIT_TOP_COMMENTS=0`)
- 자격증명이 없거나 API가 실패하면 공개 RSS로 자동 대체 (역시 장문 글만)

### Gazzetta가 계속 비어 있다면

현재는 Corriere dello Sport와 Tuttosport가 Gazzetta 공백을 대신 채웁니다. Gazzetta 피드가 살아나면 자동으로 다시 섞여 들어옵니다. 추가로 다른 매체를 넣고 싶으면 `RSS_SOURCES`에 한 항목만 추가하면 됩니다.

---

## 6. 배포 (Cloudflare Pages 권장)

NBA 데일리처럼 `*.pages.dev` 주소로 운영할 수 있습니다. 자세한 절차는 [DEPLOY.md](DEPLOY.md) 참고.

1. 이 폴더를 GitHub 저장소에 push
2. Cloudflare → **Workers & Pages → Create → Pages → Upload assets**
   - 프로젝트 이름: `roma-daily`
   - 주소: `https://roma-daily.pages.dev`
3. GitHub **Settings → Secrets and variables → Actions**
   - `OPENCODE_API_KEY`
   - `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` (선택)
   - `THESPORTSDB_API_KEY` (선택)
   - `CLOUDFLARE_API_TOKEN` (Pages Edit 권한)
   - `CLOUDFLARE_ACCOUNT_ID`
4. (선택) **Variables**
   - `CLOUDFLARE_PROJECT_NAME` (기본 `roma-daily`)
   - `OPENCODE_MODEL` (기본 `deepseek-v4.1-flash`)
   - `OPENCODE_BASE_URL` (Console을 쓸 때만)
   - `REDDIT_USER_AGENT`
5. **Actions → Roma feed → Run workflow**

자동 실행은 UTC `22:00` = **KST 07:00** 하루 1회입니다. `feed.yml`의 cron을 고치면 됩니다.

> GitHub Pages를 같이 쓰려면 Variable `DEPLOY_GITHUB_PAGES=true`를 추가하고 Settings → Pages Source를 `GitHub Actions`로 설정하세요.

- `data/articles.json`, `data/cache.json`, `data/youtube_channels.json`은 Actions 캐시로 실행 간 유지됩니다.
- 캐시가 날아가도 다음 수집 분부터 다시 쌓이므로 사이트가 깨지지는 않습니다.
- 생성물을 저장소에 커밋하지 않습니다(`.gitignore`).
- Cloudflare Pages는 정적 파일만 호스팅하고, 빌드·번역은 GitHub Actions에서 합니다.

---

## 7. 다음 단계

- [x] `matches.json` 자동 갱신 (TheSportsDB 최근 3개 라운드)
- [x] Reddit 장문 칼럼 수집 (댓글/팬반응 제외, 자격증명만 넣으면 됨)
- [x] 하루 기사 3 + 칼럼 4 쿼터 (로마 한정) + 영상 원본 4개
- [ ] 5개 미리보기 확인 후 전체 번역 품질 점검
- [ ] Gazzetta 피드 상태 모니터링, 필요하면 추가 매체 편입
- [ ] 팀별 YouTube 핸들 전부 검증 + 롱폼/쇼츠 분리 필터
- [ ] 번역 품질 검수 화면(관리자용) 또는 오역 신고 링크
- [ ] 기사 14일 후 자동 삭제, 권리자 삭제 요청 처리 절차
- [ ] `site/data/feed.json`으로 RSS/텔레그램 봇 연결

---

## 8. 저작권 메모

이 프로젝트는 세리에A·구단과 무관한 비영리 팬 사이트입니다. 기사 전문을 재배포하는 것이 아니라 **요약·번역과 원문 링크**를 제공하고, 카드마다 출처를 표시합니다. 운영 전 각 매체의 이용약관과 번역·인용 범위를 확인하고, 삭제 요청 창구를 실제 주소로 바꿔주세요. `templates/index.html` 하단의 `you@example.com`을 본인 연락처로 교체하면 됩니다.
