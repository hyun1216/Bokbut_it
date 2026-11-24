# 복붙잇 (Bokbut_it)

Windows 바탕화면 위에 포스트잇처럼 띄워놓고 사용할 수 있는 **스마트 워크 위젯(Smart Work Post-it)** 데스크톱 애플리케이션입니다.  
외부 프레임워크 없이 Python 표준 라이브러리(`tkinter`)만으로 구성되어 가볍고, `PyInstaller`를 통해 단일 `.exe` 파일로 빌드할 수 있습니다.

---

## 주요 기능

### 1. 공통 위젯 UI/UX
- **프레임리스 라벨지 디자인:** `overrideredirect(True)` 커스텀 상단바와 따뜻한 크림 페이퍼(`#FFFDF5`) · 버터 옐로우(`#F7E896`) 컬러 팔레트 적용
- **자유로운 이동 및 크기 조절:** 상단바 드래그로 위치 이동, 우측 하단 그립(`◢`) 드래그로 창 크기 조절(위치·크기 자동 저장)
- **항상 위 고정(`📌`) & 반투명 전환(`💧`):** 핀 토글로 다른 창 위 고정 여부 전환, 투명도 `0.93 ↔ 0.78 ↔ 1.0` 순환 전환
- **커스텀 미니멀 스크롤:** 기본 Windows 스크롤바 없이 마우스 휠 및 4px 커스텀 스크롤 인디케이터(클릭 홀드 연속 스크롤 · 드래그 지원) 제공
- **실시간 로컬 자동 저장:** 실행 경로 기준 `./data/widget_data.json`에 모든 데이터 자동 저장 및 로드

### 2. 탭별 기능
- **📋 복사용 탭:**
  - 자주 쓰는 텍스트를 카드 형태로 관리하고, 카드 본문 또는 복사 버튼(`➜`) 클릭 시 즉시 클립보드 복사 (`✓` 피드백 + 상단 알림 토스트)
  - 카드별 접기/펼치기(`▾`/`▸`) 지원 및 접힌 상태에서는 제목 바 클릭만으로 원클릭 복사
  - 하단 `[+ 새 복사 카드 추가]` 버튼 및 카드별 수정·삭제 지원
- **📝 메모용 탭:**
  - 멀티라인 자유 메모장, 키 입력(`KeyRelease`)마다 자동 저장 및 `자동 저장됨 ✓` 상태 표시
- **⚡ 단축어 탭:**
  - 템플릿 내 동적 변수를 실행 시점의 값으로 자동 치환해 클립보드에 복사
  - 지원 태그: `{오늘날짜}`, `{오늘날짜_간략}`, `{현재시간}`, `{요일}`, `{클립보드}`, `{클립보드_숫자만}`, `{입력:항목명}`
  - 단축어 추가/수정 팝업에서 태그 버튼 클릭 삽입 및 마우스 호버 시 실제 출력 형식 말풍선 미리보기 제공

---

## 기술 스택 (Tech Stack)

- **Language:** Python 3.11+
- **GUI:** `tkinter` (Python 표준 라이브러리)
- **Data Storage:** Local JSON (`./data/widget_data.json`)
- **Platform Integration:** `ctypes` (Windows High-DPI 스케일링 대응)
- **Packaging:** PyInstaller (`--noconsole --onefile`)

---

## 프로젝트 구조

```text
Bokbut_it/
├── main.py              # Tkinter UI, 창 제어, 탭/모달/커스텀 스크롤 구현
├── shortcut_engine.py   # 단축어 동적 변수 파싱 및 치환 엔진
├── storage.py           # 로컬 JSON 자동 저장/로드 (PyInstaller 빌드 경로 호환)
├── .gitignore
└── README.md
```

---

## 실행 및 빌드 방법

### 소스 코드로 실행
```powershell
python main.py
```

### 단일 실행 파일(`.exe`) 빌드
```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name "Bokbut_it" main.py
```
빌드 완료 후 `dist/Bokbut_it.exe`가 생성됩니다.
