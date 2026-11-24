# 복붙잇 (Bokbut_it)

Windows 바탕화면 위에 포스트잇처럼 띄워놓고 사용할 수 있는 **스마트 워크 위젯(Smart Work Widget)** 데스크톱 애플리케이션입니다.  
모던 미니멀 화이트 & 스카이블루(Apple iOS 스타일) UI와 시스템 트레이 상주 기능을 지원하며, `PyInstaller`를 통해 단일 `.exe` 파일로 빌드할 수 있습니다.

---

## 주요 기능

### 1. 공통 위젯 UI/UX
- **모던 미니멀 iOS 스타일 디자인:** 퓨어 화이트(`#FFFFFF`) 바탕, 1px 쿨그레이 보더(`#E5E7EB`), 세그먼트 탭 컨트롤(`#F3F4F6` / `#0066FF`), 둥근 알약형 카드 및 풀와이드 액션 버튼 적용
- **자유로운 이동·크기 조절·전체 접기:** 상단바 드래그로 이동, 우측 하단 그립(`◢`) 드래그로 크기 조절, 상단바 `▲/▼` 버튼으로 타이틀바만 남기는 쉐이드 모드 지원
- **항상 위 고정(`📌`) & 반투명 전환(`💧`):** 핀 토글로 최상단 고정 전환, 투명도 `0.93 ↔ 0.78 ↔ 1.0` 순환 전환
- **시스템 트레이 상주 & 작업표시줄 연동:**
  - `✕` 버튼 클릭 시 완전 종료되지 않고 작업표시줄과 화면에서 숨겨지며 Windows 시스템 트레이(`^`)에 상주
  - 트레이 메뉴: `📌 복붙잇 열기`, `⚙️ 설정`(Windows 시작 시 자동 실행 / 항상 위 / 기본 투명도), `👩‍💻 개발자 정보`, `❌ 완전 종료`
- **커스텀 미니멀 스크롤:** 기본 Windows 스크롤바 없이 마우스 휠 및 4px 커스텀 스크롤 인디케이터(클릭 홀드 연속 스크롤 · 드래그 지원) 제공
- **실시간 로컬 자동 저장:** `.exe` 실행 시 `%LOCALAPPDATA%\Bokbut_it\widget_data.json`, 개발 환경(`python main.py`)에서는 `./data/widget_data.json`에 자동 저장

### 2. 탭별 기능
- **복사용 탭:**
  - 둥근 알약형 카드 좌클릭 시 즉시 클립보드 복사 (`#EBF3FE` 배경 + `#0066FF` `✓` 피드백 및 상단 알림)
  - 좌측 화살표 배지(`›`/`⌄`) 클릭, 우클릭 또는 더블클릭으로 본문 미리보기 및 `[수정]`·`[삭제]` 아코디언 토글
  - 상단 `검색` 버튼으로 제목·본문 통합 실시간 검색 지원
- **메모용 탭:**
  - 멀티라인 자유 메모장, 키 입력(`KeyRelease`)마다 자동 저장 및 `자동 저장됨 ✓` 상태 표시
- **단축어 탭:**
  - 카드 클릭 시 템플릿 내 동적 변수를 실행 시점의 값으로 자동 치환해 클립보드에 복사
  - 지원 태그: `{오늘날짜}`, `{오늘날짜_간략}`, `{현재시간}`, `{요일}`, `{클립보드}`, `{클립보드_숫자만}`, `{입력:항목명}`
  - 단축어 추가/수정 팝업에서 태그 버튼 클릭 삽입 및 마우스 호버 시 실제 출력 형식 말풍선 미리보기 제공

---

## 기술 스택 (Tech Stack)

- **Language:** Python 3.11+
- **GUI:** `tkinter` (표준 라이브러리)
- **System Tray & Icon:** `pystray`, `Pillow` (코드 내 64×64 아이콘 동적 생성)
- **Windows Integration:** `ctypes` (High-DPI 스케일링 및 작업표시줄 연동), `winreg` (시작 프로그램 등록)
- **Data Storage:** Local JSON (`%LOCALAPPDATA%\Bokbut_it\widget_data.json`)
- **Packaging:** PyInstaller (`--noconsole --onefile`)

---

## 프로젝트 구조

```text
Bokbut_it/
├── main.py              # Tkinter UI, 트레이 상주, 탭/모달/커스텀 위젯 구현
├── shortcut_engine.py   # 단축어 동적 변수 파싱 및 치환 엔진
├── storage.py           # 로컬 JSON 자동 저장/로드 (AppData 및 개발 경로 분리)
├── .gitignore
└── README.md
```

---

## 실행 및 빌드 방법

### 의존성 설치 및 소스 코드 실행
```powershell
pip install pystray pillow
python main.py
```

### 단일 실행 파일(`.exe`) 빌드
```powershell
pip install pyinstaller
python -m PyInstaller --noconsole --onefile --clean --name "Bokbut_it" main.py
```
빌드 완료 후 `dist/Bokbut_it.exe`가 생성됩니다.
