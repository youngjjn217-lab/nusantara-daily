# Nusantara Daily

인도네시아 거주 한국인을 위한 뉴스 브리핑 앱입니다. 인도네시아 매체 뉴스를 카테고리별로 모아 한국어로 요약하고, 사실 보도와 오피니언을 구분하며, 환율·증시·세계시각을 한 화면에서 보여줍니다. 세 가지 방식으로 쓸 수 있습니다: **로컬 웹앱**, **Windows 실행 파일(.exe)**, **GitHub Pages 공개 링크**.

**버전:** v1.0.0 · **제작:** Kim Young Jin · **Copyright (c) 2026 Kim Young Jin. All rights reserved.**

## 1. 로컬 웹앱으로 실행

1. Python 3.10 이상 설치
2. `run.bat` 더블클릭 (첫 실행 시 `requirements.txt` 기준으로 패키지 자동 설치)
3. 브라우저가 자동으로 `http://127.0.0.1:8766` 를 엽니다

직접 실행하려면:

```powershell
python -m pip install -r requirements.txt
python server.py
```

## 2. Windows 실행 파일(.exe)로 만들기

Python 설치 없이 다른 사람에게 파일을 건네 바로 실행하게 하고 싶을 때 씁니다. Nusantara Market Desk와 같은 방식(PyInstaller + PyWebView 전용 창)입니다.

1. `build_exe.bat` 더블클릭 — `requirements.txt`·`requirements-desktop.txt`를 설치하고 `dist\NusantaraDaily.exe`를 만듭니다(처음엔 1~2분 걸릴 수 있습니다). 이 폴더의 `config.json`이 있으면 `dist` 폴더에 자동으로 복사됩니다.
2. `dist` 폴더 전체(또는 `NusantaraDaily.exe` + 그 옆의 `config.json`)를 다른 사람에게 전달하면, 더블클릭만으로 전용 창에서 실행됩니다.
3. `config.json`을 안 넣고 배포해도 동작합니다 — GNews 키가 없으면 자동으로 Google News RSS(요약 없음) 방식으로 대체됩니다.

같은 와이파이에 있는 핸드폰에서 보려면, PC의 내부 IP(예: `192.168.0.5`)로 `http://192.168.0.5:8766`에 접속하면 됩니다(exe가 실행 중일 때만).

## 3. GitHub Pages로 공개 링크 만들기 (서버 없음, 무료)

Render 같은 별도 호스팅 없이 GitHub만으로 동작합니다. `.github/workflows`의 두 Action이 주기적으로 뉴스(3시간마다)·환율/증시(30분마다)를 가져와 `docs/data/*.json`에 커밋하고, GitHub Pages가 `docs/` 폴더를 정적 웹사이트로 서빙합니다. 카드 인증이나 별도 서버 계정이 필요 없습니다.

저장소에는 이미 다음이 설정되어 있습니다:
- Actions 비밀값 `NUSANTARA_GNEWS_API_KEY` (GNews 키, 이미 등록됨)
- `docs/data/news.json`, `docs/data/markets.json` 초기 데이터

**GitHub Pages만 켜면 됩니다** (딱 한 번):
1. 저장소 → **Settings** → **Pages**
2. **Source**를 **Deploy from a branch**로, **Branch**를 **main** / **docs** 폴더로 선택 → **Save**
3. 1~2분 후 `https://youngjjn217-lab.github.io/nusantara-daily/` 에서 열립니다

이후로는 완전히 자동입니다. Actions 탭에서 "Update news data"/"Update market data" 워크플로가 주기적으로 실행되는 것을 볼 수 있고, 필요하면 **Run workflow** 버튼으로 즉시 갱신할 수도 있습니다.

## 동작 방식

- **뉴스 수집**: GNews.io(무료 키 설정 시 실제 요약 제공) 또는 Google News RSS(키 없이 항상 동작, 요약 없음)에서 카테고리별로 가져옵니다. 두 소스 모두 제목에 "인도네시아 신호어"(Indonesia/Jakarta/Prabowo 등)와 해당 카테고리 키워드가 함께 있는 기사만 통과시켜, 엉뚱한 나라·주제의 기사를 걸러냅니다.
- **카테고리**: 경제·증시, 정치·사회, 테크·산업, 자동차, 국제, 생활·환경
- **사실/오피니언 구분**: 제목·URL에 "opinion/column/editorial/analysis" 같은 신호가 있으면 오피니언으로 분류합니다. 기계적 휴리스틱이므로 100% 정확하지 않으며, 화면의 "사실 보도만 보기" 토글로 오피니언을 숨길 수 있습니다.
- **교차 확인**: 여러 매체가 같은 사건을 다르게 표현해도 제목의 핵심 단어 겹침을 기준으로 하나의 카드로 묶고, "N개 매체 교차 확인"과 각 매체명을 표시합니다.
- **한국어 요약**: [MyMemory](https://mymemory.translated.net) 무료 번역 API로 제목·요약을 한국어로 옮깁니다. 키/가입 불필요. 실제로 화면에 보이는 기사만 번역해 요청 수를 아끼며, 번역 결과는 로컬에 캐시됩니다. 무료 한도 초과 시 자동으로 원문(영어)을 보여줍니다.
- **환율·증시**: Yahoo Finance(yfinance, 키 불필요)에서 USD/IDR, USD/KRW을 가져와 1,000 IDR→KRW을 계산하고, IHSG(자카르타종합지수)·KOSPI 지수를 함께 보여줍니다. 15분마다 자동 갱신됩니다.
- **세계 시각**: 자카르타(WIB)·발리(WITA)·서울(KST) — 인도네시아는 시간대가 3개라 발리 기준도 별도로 표시합니다. 브라우저 자체 시계 기반이라 서버 호출이 필요 없습니다.
- **스크랩**: 카드의 🔖 아이콘으로 저장하면 브라우저 로컬 저장소(localStorage)에 남습니다. 상단 "스크랩" 버튼으로 저장한 기사만 모아볼 수 있습니다. 이 브라우저/기기에만 저장되며, 다른 기기와는 동기화되지 않습니다.
- **기본 화면 제한**: "전체" 탭 + 검색 없음 상태에서는 최신 15건만 보여줍니다(갱신·번역 비용 절약). 카테고리를 선택하거나 검색하면 해당 범위를 모두 보여줍니다.
- 서버 시작 시 한 번 가져오고, 이후 백그라운드에서 자동 갱신합니다(GNews 키 없을 때 20분, 있을 때 3시간 — 무료 API 한도를 아끼기 위함). 우측 상단 "새로고침" 버튼으로 즉시 갱신할 수 있습니다.

## 진짜 요약(GNews.io) 켜기 (선택)

이 폴더에는 이미 `config.json`에 GNews.io 키가 들어 있습니다(이전에 발급받은 키를 재사용했습니다). 다른 키로 바꾸려면:

1. https://gnews.io 에서 무료 계정을 만들고 API 키를 복사합니다.
2. `config.json`의 `gnews_api_key` 값을 새 키로 바꿉니다.
3. `run.bat`을 다시 실행합니다.

키가 없거나 잘못되었거나 한도를 넘으면 자동으로 Google News RSS(요약 없음) 방식으로 되돌아가므로 앱은 계속 동작합니다.

## 제한 사항

- 사실/오피니언 구분과 교차 확인은 제목 기반 휴리스틱입니다. 법적·언론적 팩트체크가 아니며, 정확한 판단은 항상 "원문 보기"로 확인해야 합니다.
- 번역은 기계번역이라 뉘앙스가 원문과 다를 수 있습니다.
- **자동차** 카테고리는 다른 카테고리보다 보도량이 적어 기사 수가 적을 때가 많습니다.
- GNews.io 무료 플랜은 최근 12시간 이내 기사에 접근 지연이 있어 특정 카테고리가 일시적으로 비어 보일 수 있습니다(이 경우 자동으로 Google News RSS로 대체).
- 환율·증시는 Yahoo Finance 공개 시세이며 실제 거래/송금에 쓸 환율과 다를 수 있습니다. 정확한 금액은 은행·환전소에서 확인하세요.

## 구조

```
Nusantara Daily/
  server.py                   FastAPI 서버 (로컬 웹앱·exe 공용)
  app_desktop.py               PyWebView 데스크톱 진입점 (exe용)
  news_fetcher.py               뉴스 수집·분류·교차확인·번역·캐싱
  market_fetcher.py             환율·증시 시세 수집·캐싱 (yfinance)
  build_static_data.py          GitHub Pages용 정적 JSON 생성 스크립트
  static/                       로컬 웹앱·exe 프론트엔드
  docs/                         GitHub Pages 프론트엔드 + data/*.json
  .github/workflows/            뉴스·환율 자동 갱신 Action
  run.bat                       로컬 웹앱 실행
  build_exe.bat                 .exe 빌드
  requirements.txt               웹앱/exe/Pages 공용 의존성
  requirements-desktop.txt       exe 빌드 전용 의존성 (pywebview, pyinstaller)
```
