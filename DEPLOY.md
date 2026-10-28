# 배포·운영 가이드 (GitHub Pages)

현재 프로젝트는 **정적 HTML + GitHub Actions** 구조입니다. 서버·DB 없이 GitHub Pages로 무료 공개할 수 있습니다.

- 저장소: https://github.com/hwajungsong951-eng/roma-daily
- 예상 주소: `https://hwajungsong951-eng.github.io/roma-daily/`
- 자동 갱신: 매일 **07:00 KST** (UTC 22:00)

---

## 1. 최초 설정 (한 번만)

### 1) OPENCODE_API_KEY Secret 추가

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|---|---|
| `OPENCODE_API_KEY` | 로컬 `.env`의 `oc_sk_...` 값 |

> 키를 코드나 README에 직접 쓰지 마세요. Secret에만 넣습니다.

### 2) GitHub Pages 켜기

저장소 → **Settings → Pages**

- **Build and deployment → Source**: `GitHub Actions`
- 별도 브랜치 선택은 필요 없습니다.

### 3) 워크플로 실행

저장소 → **Actions → Roma feed → Run workflow**

성공하면:

```text
https://hwajungsong951-eng.github.io/roma-daily/
```

> 첫 실행은 2~5분 정도 걸릴 수 있습니다.

---

## 2. 자동 실행

`.github/workflows/feed.yml`의 스케줄:

```yaml
schedule:
  - cron: "0 22 * * *"   # UTC 22:00 = KST 07:00
```

동작 순서:

1. 경기 결과 갱신 (`matches.json`)
2. RSS·Reddit·YouTube 수집
3. 번역 7개 (기사 3 + 칼럼 4)
4. 남자축구 영상 4개 선별
5. 정적 사이트 빌드
6. GitHub Pages 배포

`main` 브랜치에 push해도 한 번 실행됩니다.

---

## 3. 수동 갱신

- **GitHub 웹**: Actions → Roma feed → **Run workflow**
- **로컬**: `update-feed.bat` 실행 후 `start-site.bat`으로 확인

---

## 4. Secrets / Variables

**Settings → Secrets and variables → Actions**

### Secrets

| 이름 | 필수 | 설명 |
|---|---|---|
| `OPENCODE_API_KEY` | 필수 | OpenCode Go API 키 (`oc_sk_...`) |
| `REDDIT_CLIENT_ID` | 선택 | Reddit 장문 칼럼 수집용 |
| `REDDIT_CLIENT_SECRET` | 선택 | 위와 동일 |
| `THESPORTSDB_API_KEY` | 선택 | 없으면 무료 test key `123` |

### Variables (선택)

| 이름 | 기본값 |
|---|---|
| `OPENCODE_MODEL` | `deepseek-v4.1-flash` |
| `OPENCODE_REASONING_EFFORT` | `none` |
| `REDDIT_USER_AGENT` | 기본 UA |

---

## 5. 커스텀 도메인 (선택)

예: `roma.example.com`

1. 도메인 구매 (Cloudflare Registrar, Namecheap 등)
2. DNS에 `CNAME` 레코드 추가
   - 이름: `roma`
   - 값: `hwajungsong951-eng.github.io`
3. 저장소 → **Settings → Pages → Custom domain**에 도메인 입력
4. **Enforce HTTPS** 체크

도메인 비용은 보통 연 $10~20입니다.

---

## 6. 비용

| 항목 | 비용 |
|---|---|
| GitHub Pages | 무료 |
| GitHub Actions (public repo) | 무료 |
| OpenCode Go API | 월 $0.2~0.3 수준 |
| 도메인 | 연 $10~20 (선택) |

---

## 7. 운영 체크리스트

### 매일

- Actions 실행 성공 여부 확인
- 사이트 상단 `업데이트` 시간 확인
- 새 글 7개 + 영상 4개 확인

### 매주

- 번역 품질 샘플 확인
- 깨진 RSS/YouTube 채널 확인
- `data/articles.json` 크기 확인 (7일 보관, 최대 250개)

### 매월

- OpenCode 사용량/비용 확인
- `THESPORTSDB_API_KEY` rate limit 확인
- 도메인·HTTPS 만료 확인

### Actions가 실패하면

- **Actions → 실패한 run → 로그** 확인
- `401`: `OPENCODE_API_KEY` 문제
- RSS 0개: 원문 사이트 차단 또는 피드 변경
- YouTube 0개: 채널 페이지 구조 변경
- Pages 404: Settings → Pages Source가 `GitHub Actions`인지 확인

---

## 8. 데이터 보관

`data/articles.json`과 `data/cache.json`은 GitHub Actions 캐시에 의존합니다.

- 보통은 유지되지만, 캐시가 삭제되면 이전 글이 사라질 수 있습니다.
- 장기 보관이 중요해지면:
  1. `data/articles.json`을 별도 브랜치에 커밋하거나
  2. Cloudflare R2 / Supabase Storage에 저장

---

## 9. 공개 운영 주의사항

- 원문 링크와 출처를 항상 표시
- 유료 기사 전문 번역은 피하기
- 이미지는 원본 URL을 사용 (별도 저장 안 함)
- Reddit 작성자 표시
- 권리자 삭제 요청 시 24시간 내 삭제
- 사이트 하단 `you@example.com`을 실제 연락처로 교체

각 매체의 이용약관과 번역·인용 범위를 확인하는 것을 권장합니다.

---

## 10. 나중에 Cloudflare Pages를 쓰려면

GitHub Pages로 먼저 공개한 뒤, 원하면 `*.pages.dev` 주소를 추가할 수 있습니다.

1. Cloudflare에서 Pages 프로젝트 생성 (`roma-daily`)
2. `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`를 GitHub Secrets에 추가
3. 워크플로에 Cloudflare 배포 단계 추가

현재 워크플로는 GitHub Pages만 배포합니다.
