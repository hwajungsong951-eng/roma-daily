# 배포·운영 가이드

현재 프로젝트는 **정적 HTML + GitHub Actions** 구조라서 서버·DB 없이 무료로 운영할 수 있습니다.

---

## 추천: Cloudflare Pages (`*.pages.dev`)

NBA 데일리(`nba-feed.pages.dev`)와 같은 방식입니다. **빌드는 GitHub Actions에서 하고, 결과물만 Cloudflare Pages에 올립니다.**

### 1) Cloudflare Pages 프로젝트 만들기

1. https://dash.cloudflare.com 접속
2. **Workers & Pages → Create → Pages → Upload assets**
3. 프로젝트 이름: `roma-daily`
4. 생성 후 주소: `https://roma-daily.pages.dev`

> 프로젝트 이름을 바꾸면 `https://<프로젝트명>.pages.dev`가 됩니다.

### 2) API 토큰 만들기

1. Cloudflare 오른쪽 위 프로필 → **My Profile → API Tokens**
2. **Create Token → Custom token**
3. 권한:
   - **Account → Cloudflare Pages → Edit**
4. Account Resources: 본인 계정 선택
5. 생성된 토큰 복사

Account ID는 Cloudflare 대시보드 오른쪽 **Account ID**에서 확인합니다.

### 3) GitHub Secrets 추가

저장소 → **Settings → Secrets and variables → Actions**

| 종류 | 이름 | 값 |
|---|---|---|
| Secret | `CLOUDFLARE_API_TOKEN` | 위에서 만든 토큰 |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID |
| Variable | `CLOUDFLARE_PROJECT_NAME` | `roma-daily` (선택) |

`CLOUDFLARE_PROJECT_NAME`을 생략하면 기본값 `roma-daily`를 씁니다.

### 4) 배포

**Actions → Roma feed → Run workflow**

성공하면:

```text
https://roma-daily.pages.dev
```

> GitHub Pages는 기본적으로 꺼져 있습니다. GitHub Pages도 같이 쓰려면 저장소 Variable에 `DEPLOY_GITHUB_PAGES=true`를 추가하고 Pages Source를 `GitHub Actions`로 설정하세요.

### 5) 커스텀 도메인 (선택)

Cloudflare Pages → 프로젝트 → **Custom domains** → `roma.example.com` 추가  
도메인을 Cloudflare에서 관리 중이면 DNS가 자동으로 잡힙니다.

---

## GitHub Pages로 배포하기 (대안)

### 준비

- GitHub 계정
- `seriea-feed` 폴더를 **저장소 루트**로 올려야 합니다.
  - `project/seriea-feed/.github/workflows/feed.yml` 구조가 되어야 Actions가 인식합니다.
- `.env`는 절대 올리지 마세요. `.gitignore`에 이미 포함되어 있습니다.

### 저장소 만들기

GitHub에서 새 저장소를 만든 뒤:

```powershell
cd D:\MyData\Documents\project\seriea-feed
git init
git add .
git commit -m "feat: Roma daily feed"
git branch -M main
git remote add origin https://github.com/<본인계정>/<저장소>.git
git push -u origin main
```

### Pages 켜기

1. 저장소 → **Settings → Pages**
2. **Build and deployment → Source: GitHub Actions**
3. **Actions → Roma feed → Run workflow** 수동 1회 실행
4. 배포가 끝나면 `https://<계정>.github.io/<저장소>/` 접속

> 저장소가 **private**이면 GitHub Pages 공개에 유료 플랜이 필요할 수 있습니다.  
> 공개 서비스라면 public 저장소가 가장 간단합니다.

---

## 2. Secrets / Variables

**Settings → Secrets and variables → Actions**

### Secrets

| 이름 | 필수 | 설명 |
|---|---|---|
| `OPENCODE_API_KEY` | 필수 | OpenCode Go API 키 (`oc_sk_...`) |
| `REDDIT_CLIENT_ID` | 선택 | Reddit 장문 칼럼 수집용 |
| `REDDIT_CLIENT_SECRET` | 선택 | 위와 동일 |
| `THESPORTSDB_API_KEY` | 선택 | 없으면 무료 test key `123` |
| `CLOUDFLARE_API_TOKEN` | Cloudflare 배포 시 필수 | Pages Edit 권한 토큰 |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 배포 시 필수 | Cloudflare 계정 ID |

### Variables (선택)

| 이름 | 기본값 |
|---|---|
| `OPENCODE_MODEL` | `deepseek-v4.1-flash` |
| `OPENCODE_REASONING_EFFORT` | `none` |
| `OPENCODE_BASE_URL` | Go 엔드포인트 |
| `REDDIT_USER_AGENT` | 기본 UA |

⚠️ API 키를 코드·README·채팅에 붙이지 마세요. Actions Secret에만 넣습니다.

---

## 3. 자동 실행

`.github/workflows/feed.yml`:

```yaml
schedule:
  - cron: "0 22 * * *"   # UTC 22:00 = KST 07:00, 하루 1회
```

동작 순서:

1. 경기 결과 자동 갱신 (`matches.json`)
2. RSS·Reddit·YouTube 수집
3. 기사 3 + 칼럼 4 번역 (하루 7개)
4. 영상 4개 원본 선별
5. 정적 사이트 빌드
6. GitHub Pages 배포

수동 실행은 **Actions → Roma feed → Run workflow**에서 합니다.

---

## 4. 커스텀 도메인 (선택)

예: `roma.example.com`

1. 도메인 구매 (Cloudflare Registrar, Namecheap 등)
2. DNS에서 `CNAME` 레코드:
   - 이름: `roma`
   - 값: `<계정>.github.io`
3. GitHub Pages → **Custom domain**에 도메인 입력
4. **Enforce HTTPS** 체크

도메인 비용은 보통 연 $10~20 수준입니다.

---

## 5. 비용

| 항목 | 비용 |
|---|---|
| GitHub Pages | 무료 |
| GitHub Actions (public repo) | 무료 |
| OpenCode Go API | 월 $0.2~0.3 수준 (하루 7개 기준) |
| 도메인 | 연 $10~20 (선택) |
| 이미지/영상 | 원본 URL 핫링크, 저장 비용 없음 |

Go 플랜 $80 한도 안에서 충분히 운영됩니다.

---

## 6. 운영 체크리스트

### 매일

- Actions 실행 성공 여부 확인
- 사이트 상단 `업데이트` 시간 확인
- 새 글 7개 + 영상 4개가 올라왔는지 확인

### 매주

- 번역 품질 샘플 확인 (특히 인터뷰·팬 칼럼)
- 깨진 RSS/YouTube 채널 확인
- `data/articles.json` 크기 확인 (7일 보관, 최대 250개)

### 매월

- OpenCode 사용량/비용 확인
- `THESPORTSDB_API_KEY` rate limit 여부 확인
- 도메인·HTTPS 만료 확인

### Actions가 실패하면

- **Actions → 실패한 run → 로그** 확인
- `401`: OpenCode 키 문제
- RSS 0개: 원문 사이트 차단/피드 변경
- YouTube 0개: 채널 페이지 구조 변경
- Pages 404: Settings → Pages Source가 `GitHub Actions`인지 확인

---

## 7. 데이터 보관의 한계

현재 `data/articles.json`과 `data/cache.json`은 **Actions 캐시**에 의존합니다.

- 보통은 유지되지만, GitHub 캐시가 evict되면 이전 글이 사라질 수 있습니다.
- 공개 서비스에서 장기 보관이 중요해지면:
  1. `data/articles.json`을 별도 브랜치에 커밋하거나
  2. Cloudflare R2 / Supabase Storage에 저장하거나
  3. Cloudflare D1 같은 무료 DB로 이전

MVP 단계에서는 현재 캐시 구조로 충분합니다.

---

## 8. 다른 사람들이 쓰게 할 때

### 바로 되는 것

- URL 공유
- 모바일/데스크톱 반응형
- 로그인 없음
- 검색·팀 필터·태그 필터

### 추가로 권장

- **Cloudflare Web Analytics** 또는 Plausible: 개인정보 친화적 방문자 통계
- **UptimeRobot**: 사이트 다운 알림
- **RSS 출력**: `site/data/feed.json`을 RSS로 변환
- **텔레그램/디스코드 봇**: 새 글 7개 요약 전송
- **오역 신고 링크**: 카드 하단에 메일 링크

### 아직 없는 것

- 댓글/회원 기능 (의도적으로 없음)
- 검색 엔진 최적화용 sitemap
- 이미지 자체 호스팅

---

## 9. 공개 운영 시 주의사항

이 사이트는 타사 기사·블로그·Reddit 글을 **번역·요약**해 보여줍니다.

- 원문 링크와 출처를 항상 표시
- 광고·구독 유도 문구는 제거
- 유료 기사 전문 번역은 피하기
- 이미지는 원본 URL을 핫링크 (별도 저장 안 함)
- Reddit 작성자 표시
- 권리자 삭제 요청 시 24시간 내 삭제
- 사이트 하단 `you@example.com`을 실제 연락처로 교체

공개 서비스로 키우기 전에 각 매체의 이용약관과 번역·인용 범위를 확인하는 것을 권장합니다. 필요하면 본문 번역 분량을 줄이고 “핵심 요약 + 짧은 인용” 형태로 조정하세요.

---

## 10. 다음 단계 추천

1. public 저장소로 배포
2. 1주일 운영하며 번역 품질 확인
3. 커스텀 도메인 연결
4. Cloudflare Analytics 추가
5. 필요하면 RSS/텔레그램 알림
6. 데이터 보관을 R2/Supabase로 이전
