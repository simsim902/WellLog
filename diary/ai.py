"""Gemini API로 최근 기록을 요약하고 조언을 받아오는 코드.

실패했을 때 자세한 원인은 서버 로그에만 남기고, 화면에는 고정 문구만 보여준다.
(에러 내용에 내부 정보가 섞여 있을 수 있어서 사용자에게 그대로 보여주지 않는다.)
"""
import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# 모델 이름은 자주 바뀌므로 .env의 GEMINI_MODEL로 바꿀 수 있게 해 둔다.
DEFAULT_MODEL = 'gemini-3.5-flash-lite'

TIMEOUT_MS = 15_000       # AI 응답을 최대 15초까지만 기다린다 (SDK는 밀리초 단위)
MIN_LOGS = 3              # 리포트를 만들려면 최근 7일 중 최소 이만큼의 기록이 필요
MAX_MEMO_CHARS = 300      # 메모가 너무 길어도 AI에 보내는 양을 제한

# 화면에 보여줄 문구 (views.py에서도 사용)
FRIENDLY_ERROR = '지금은 리포트를 만들 수 없어요. 잠시 후 다시 시도해 주세요.'

SYSTEM_INSTRUCTION = (
    '너는 감정 일기 앱 WellLog의 따뜻한 도우미야. '
    '사용자의 최근 7일 기분 기록(점수 1~5, 5가 가장 좋음)과 메모를 보고, '
    '한국어로 다음 두 부분을 써 줘.\n'
    '1) 요약: 이번 주 기분 흐름을 2~3문장으로\n'
    '2) 조언: 지금 해볼 만한 작고 구체적인 행동 2~3가지\n'
    '의학적 진단은 하지 말고, 너무 길지 않게 써. '
    '사용자가 많이 힘들어 보이면 주변 사람이나 전문가의 도움을 받아 보라고 부드럽게 권해 줘.'
)


class AIReportError(Exception):
    """AI 리포트를 만들지 못했을 때(키 오류, 네트워크 오류, 시간 초과 등).

    메시지는 로그용이다. 사용자 화면에는 FRIENDLY_ERROR만 보여준다.
    """


def build_prompt(logs):
    lines = []
    for log in logs:
        memo = log.memo.strip()[:MAX_MEMO_CHARS] or '(메모 없음)'
        lines.append(f'- {log.date:%m/%d}: 점수 {log.score}, 메모: {memo}')
    return '최근 7일 기록이야:\n' + '\n'.join(lines)


def generate_report(logs):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        logger.error('AI 리포트 실패: GEMINI_API_KEY가 설정되지 않았습니다.')
        raise AIReportError('GEMINI_API_KEY 없음')

    model = os.environ.get('GEMINI_MODEL', DEFAULT_MODEL)
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
        response = client.models.generate_content(
            model=model,
            contents=build_prompt(logs),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                max_output_tokens=800,
            ),
        )
        text = (response.text or '').strip()
    except Exception as exc:  # 키 오류/네트워크 끊김/시간 초과/응답 차단 등 전부 같은 방식으로 처리
        logger.exception('AI 리포트 실패 (model=%s): %s', model, type(exc).__name__)
        raise AIReportError(type(exc).__name__) from exc

    if not text:
        logger.error('AI 리포트 실패: 빈 응답 (model=%s)', model)
        raise AIReportError('빈 응답')
    return text
