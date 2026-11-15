# WellLog

감정 일기와 AI 리포트 웹서비스

하루의 기분을 점수와 메모로 기록하고, 그래프와 캘린더로 흐름을 돌아보며, 최근 일주일 기록을 AI가 요약하고 조언해 주는 웹서비스입니다.

## 주요 기능

- **회원가입 / 로그인 / 로그아웃**: Django 기본 인증 사용
- **기분 기록**: 날짜, 점수(1~5), 메모 입력. 하루에 기록 1개만 가능
- **내 기록 목록**: 로그인한 본인의 기록만 조회, 수정, 삭제
- **주간 기분 그래프**: 최근 7일의 기분 점수를 Chart.js 꺾은선 그래프로 표시
- **월간 캘린더**: 기록한 날을 점수별 색깔로 표시하고, 이전 달 / 다음 달 이동
- **AI 리포트**: 버튼 한 번으로 최근 7일 기록을 AI가 요약하고 조언 (최근 7일 중 3일 이상 기록 필요)
- **오류 대응**: AI 호출이 실패해도(키 오류, 인터넷 끊김, 시간 초과 등) 앱이 멈추지 않고 안내 문구를 표시

## 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| 백엔드 | Django 5.2 (Python) |
| 데이터베이스 | SQLite |
| 프론트엔드 | HTML, CSS, JavaScript (프레임워크 없음) |
| 그래프 | Chart.js 4.4.1 (프로젝트에 포함, 인터넷 없이 동작) |
| AI | Gemini API (`google-genai` SDK) |

## 설치와 실행 방법

아래는 Windows PowerShell 기준입니다. Python 3.11 이상이 필요합니다.

```powershell
# 1. 저장소 내려받기
git clone https://github.com/simsim902/WellLog.git
cd WellLog

# 2. 가상환경 만들고 켜기
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. 필요한 패키지 설치
pip install -r requirements.txt

# 4. .env 파일 만들기
Copy-Item .env.example .env
#    메모장 등으로 .env를 열어 GEMINI_API_KEY= 뒤에 본인의 API 키를 입력
#    (API 키 발급: https://aistudio.google.com/apikey)

# 5. 데이터베이스 만들기
python manage.py migrate

# 6. 서버 실행
python manage.py runserver
```

브라우저에서 http://127.0.0.1:8000/ 에 접속합니다.

> `.\venv\Scripts\Activate.ps1`이 보안 정책 때문에 막히면, PowerShell에서 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`를 한 번 실행한 뒤 다시 시도하세요.



## 폴더 구조

```
WellLog/
├─ config/                    프로젝트 설정 (settings.py, urls.py)
├─ diary/                     감정 일기 앱
│  ├─ management/commands/
│  │  └─ seed_demo.py         시연용 샘플 데이터 생성 명령어
│  ├─ migrations/             데이터베이스 변경 기록
│  ├─ static/diary/
│  │  ├─ style.css            화면 스타일
│  │  ├─ stats.js             주간 그래프와 AI 리포트 버튼 동작
│  │  └─ vendor/              Chart.js (외부 라이브러리 파일)
│  ├─ templates/
│  │  ├─ base.html            공통 레이아웃
│  │  ├─ diary/               기록 목록, 입력 폼, 삭제 확인, 통계 화면
│  │  └─ registration/        로그인, 회원가입 화면
│  ├─ ai.py                   Gemini API 호출과 실패 처리
│  ├─ forms.py                입력 폼과 하루 1개 제한 검사
│  ├─ models.py               MoodLog 모델 (user, date, score, memo)
│  ├─ views.py                화면별 처리 로직
│  ├─ urls.py                 주소 연결
│  └─ tests.py                자동 테스트
├─ docs/
│  ├─ poster/                 포스터 PDF (추가 예정)
│  └─ report/                 결과보고서 PDF (추가 예정)
├─ .env.example               .env 파일 작성 예시 (API 키는 비어 있음)
├─ manage.py                  Django 실행 도구
└─ requirements.txt           필요한 패키지 목록
```

## 팀원

- 32212410 심조완

---

[시연 영상](https://youtu.be/4Ryg6eZc1lE)
