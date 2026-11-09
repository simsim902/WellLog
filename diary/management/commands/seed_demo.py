import math
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from diary.models import MoodLog

DEMO_USERNAME = 'demo'
DEMO_PASSWORD = 'demo1234!'
DAYS = 30

# 요일별 기본 기분 (월=0 ... 일=6): 주중엔 낮고 주말엔 높게
WEEKDAY_BASE = {0: 2.0, 1: 2.4, 2: 2.8, 3: 3.0, 4: 3.6, 5: 4.4, 6: 4.7}

MEMOS = {
    1: ['발표 준비로 밤을 새서 너무 지쳤다.', '하루 종일 아무것도 하기 싫었다.', '사소한 일에 계속 예민해졌다.'],
    2: ['과제가 밀려서 마음이 무거웠다.', '잠을 설쳐서 하루 종일 피곤했다.', '수업이 길어서 집중이 잘 안 됐다.'],
    3: ['평범한 하루. 크게 좋지도 나쁘지도 않았다.', '점심 먹고 산책을 조금 했다.', '할 일을 하나씩 끝냈다.'],
    4: ['친구랑 저녁 먹으면서 수다 떨어서 즐거웠다.', '운동하고 나니 개운했다.', '오랜만에 여유롭게 카페에 다녀왔다.'],
    5: ['가족이랑 나들이 가서 정말 행복했다.', '좋아하는 영화를 보고 푹 쉬었다. 완전 충전!', '작품 작업이 잘 풀려서 뿌듯한 하루였다.'],
}


def make_scores(rng):
    """30일치 점수를 만든다: 요일 경향 + 완만한 오르내림 + 약간의 무작위."""
    scores = []
    for i in range(DAYS):
        day_offset = DAYS - 1 - i  # i=0이 가장 오래된 날
        weekday = (timezone.localdate() - timedelta(days=day_offset)).weekday()
        wave = 0.6 * math.sin(i / DAYS * 2 * math.pi * 1.5)
        value = WEEKDAY_BASE[weekday] + wave + rng.gauss(0, 0.9)
        scores.append(min(5, max(1, round(value))))

    # 1~5점이 모두 한 번 이상 나오도록 보정 (시연 때 그래프/달력 색이 다양하게 보이게)
    for wanted in range(1, 6):
        if wanted in scores:
            continue
        # 중복된 점수 중에서 원하는 점수와 가장 가까운 날을 골라 바꾼다
        candidates = [i for i, s in enumerate(scores) if scores.count(s) > 1]
        target = min(candidates, key=lambda i: abs(scores[i] - wanted))
        scores[target] = wanted
    return scores


class Command(BaseCommand):
    help = 'demo 계정을 만들고 최근 30일치 시연용 기분 기록을 넣습니다. (여러 번 실행해도 안전)'

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(2026)  # 고정 시드: 실행할 때마다 같은 데이터
        today = timezone.localdate()

        user, created = User.objects.get_or_create(username=DEMO_USERNAME)
        user.set_password(DEMO_PASSWORD)  # 비밀번호를 항상 알려진 값으로 맞춘다
        user.save()

        scores = make_scores(rng)
        blank_days = 0
        for i, score in enumerate(scores):
            day = today - timedelta(days=DAYS - 1 - i)
            # 약 15%는 메모를 비워 두어 "메모 없는 기록"도 보이게
            memo = '' if rng.random() < 0.15 else rng.choice(MEMOS[score])
            blank_days += memo == ''
            # 같은 날짜가 이미 있으면 덮어쓰기 (demo 계정의 기록만 대상)
            MoodLog.objects.update_or_create(
                user=user, date=day, defaults={'score': score, 'memo': memo},
            )

        counts = {s: scores.count(s) for s in range(1, 6)}
        self.stdout.write(self.style.SUCCESS(
            f'{"새로 만든" if created else "기존"} demo 계정에 {DAYS}일치 기록을 넣었어요 '
            f'(메모 없는 날 {blank_days}일).'
        ))
        self.stdout.write(f'점수 분포: {counts}')
        self.stdout.write(f'아이디: {DEMO_USERNAME}  비밀번호: {DEMO_PASSWORD}')
