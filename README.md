# AI 시민제안 Co-Pilot

김포도시관리공사의 AI 기반 시민제안서 작성 도우미 프로토타입

## 프로젝트 개요

이 프로젝트는 시민이 아이디어의 핵심만 입력하면, AI가 멋진 제안서 초안을 만들어주는 서비스입니다. Google Gemini API를 사용하여 텍스트를 생성하고, pywin32를 통해 한글(HWP) 파일을 자동으로 생성합니다.

## 주요 기능

- **AI 제안서 생성**: Google Gemini API를 통한 지능형 텍스트 생성
- **한글 파일 자동 생성**: pywin32를 통한 HWP 파일 생성 및 다운로드
- **사용자 친화적 UI**: 반응형 웹 인터페이스
- **자동 저장**: 로컬 스토리지를 통한 입력값 보존

## 시스템 요구사항

- **운영체제**: Windows (pywin32 라이브러리 요구)
- **Python**: 3.8 이상
- **한글과컴퓨터 오피스**: 한글 프로그램 설치 필요
- **Google Gemini API**: API 키 필요

## 설치 및 설정

### 1. 저장소 클론
```bash
git clone <repository-url>
cd ai-citizen-proposal-copilot
```

### 2. Python 가상환경 생성 및 활성화
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 3. 패키지 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 추가하세요:
```
GEMINI_API_KEY=your_gemini_api_key_here
FLASK_ENV=development
FLASK_DEBUG=True
```

### 5. 한글 서식 파일 준비
- `시민제안서식.hwp` 파일을 프로젝트 루트 디렉토리에 배치
- 파일 내에 다음 누름틀들이 포함되어 있어야 합니다:
  - `{{제안명}}`
  - `{{현황및문제점}}`
  - `{{개선방안}}`
  - `{{기대효과}}`

## 실행 방법

### 백엔드 서버 실행
```bash
python app.py
```

### 프런트엔드 실행
웹 브라우저에서 `index.html` 파일을 열거나, 로컬 웹 서버를 사용하세요:
```bash
# Python 내장 서버 사용
python -m http.server 8000
```

## API 엔드포인트

### 1. 제안서 텍스트 생성
- **URL**: `POST /generate-text`
- **요청 본문**:
```json
{
  "problem": "현황 및 문제점",
  "solution": "개선 방안",
  "effect": "기대 효과",
  "title_idea": "제안 제목 아이디어"
}
```
- **응답**:
```json
{
  "title": "생성된 제안명",
  "problem": "생성된 현황 및 문제점",
  "solution": "생성된 개선 방안",
  "effect": "생성된 기대 효과"
}
```

### 2. HWP 파일 다운로드
- **URL**: `POST /download-hwp`
- **요청 본문**:
```json
{
  "title": "제안명",
  "problem": "현황 및 문제점",
  "solution": "개선 방안",
  "effect": "기대 효과"
}
```
- **응답**: HWP 파일 (바이너리)

### 3. 서버 상태 확인
- **URL**: `GET /health`
- **응답**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00",
  "hwp_template_exists": true
}
```

## 프로젝트 구조

```
ai-citizen-proposal-copilot/
├── app.py                 # Flask 백엔드 서버
├── index.html            # 프런트엔드 메인 페이지
├── style.css             # 스타일시트
├── script.js             # JavaScript 기능
├── requirements.txt      # Python 패키지 의존성
├── 시민제안서식.hwp      # 한글 서식 파일
└── README.md            # 프로젝트 문서
```

## 개발자 정보

- **프로젝트명**: AI 시민제안 Co-Pilot
- **개발기관**: 김포도시관리공사
- **버전**: 1.0.0
- **개발일**: 2024년

## 라이선스

이 프로젝트는 김포도시관리공사의 내부 프로토타입입니다.

## 문제 해결

### 자주 발생하는 문제

1. **GEMINI_API_KEY 오류**
   - 환경 변수가 올바르게 설정되었는지 확인
   - API 키가 유효한지 확인

2. **한글 파일 생성 오류**
   - 한글 프로그램이 설치되어 있는지 확인
   - `시민제안서식.hwp` 파일이 프로젝트 루트에 있는지 확인
   - 누름틀 이름이 정확한지 확인

3. **CORS 오류**
   - Flask-CORS가 설치되어 있는지 확인
   - 프런트엔드와 백엔드가 같은 도메인에서 실행되는지 확인

## 향후 개발 계획

- [ ] 다국어 지원 (영어, 중국어)
- [ ] 모바일 앱 개발
- [ ] 제안서 템플릿 다양화
- [ ] 사용자 인증 시스템
- [ ] 제안서 히스토리 관리
