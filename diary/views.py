import calendar
import logging
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .ai import FRIENDLY_ERROR, MIN_LOGS, AIReportError, generate_report
from .forms import MoodLogForm, SignUpForm
from .models import MoodLog

logger = logging.getLogger(__name__)


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # 가입하면 바로 로그인
            return redirect('log_list')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def log_list(request):
    # 로그인한 본인 기록만 가져온다
    logs = MoodLog.objects.filter(user=request.user)
    return render(request, 'diary/log_list.html', {'logs': logs})


def _parse_month(value):
    """'2026-11' 형태를 (2026, 11)로 바꾼다. 잘못된 값이면 이번 달."""
    today = timezone.localdate()
    try:
        year, month = (int(x) for x in value.split('-'))
        date(year, month, 1)  # 유효한 달인지 확인
        # 너무 먼 연도는 이전/다음 달 계산에서 날짜 범위를 넘어 오류가 나므로 막는다
        if not 1900 <= year <= 2100:
            raise ValueError
        return year, month
    except (AttributeError, ValueError):
        return today.year, today.month


@login_required
def stats(request):
    today = timezone.localdate()

    # --- 주간 그래프: 오늘 포함 최근 7일 ---
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    week_scores = dict(
        MoodLog.objects.filter(user=request.user, date__in=days).values_list('date', 'score')
    )
    chart = {
        'labels': [f'{d.month}/{d.day}' for d in days],
        'scores': [week_scores.get(d) for d in days],  # 기록 없는 날은 None(null)
    }
    has_logs = MoodLog.objects.filter(user=request.user).exists()
    week_empty = all(s is None for s in chart['scores'])

    # --- 월간 캘린더 ---
    year, month = _parse_month(request.GET.get('month'))
    logs = {
        log.date: log
        for log in MoodLog.objects.filter(user=request.user, date__year=year, date__month=month)
    }
    weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year, month):  # 일요일 시작
        weeks.append([
            {
                'date': d,
                'in_month': d.month == month,
                'log': logs.get(d),
                'today': d == today,
            }
            for d in week
        ])

    first = date(year, month, 1)
    prev_month = first - timedelta(days=1)
    next_month = first + timedelta(days=31)
    context = {
        'chart': chart,
        'has_logs': has_logs,
        'week_empty': week_empty,
        'weeks': weeks,
        'year': year,
        'month': month,
        'prev': f'{prev_month.year}-{prev_month.month:02d}',
        'next': f'{next_month.year}-{next_month.month:02d}',
    }
    return render(request, 'diary/stats.html', context)


@login_required
@require_POST
def ai_report(request):
    """최근 7일 기록을 AI에 보내고 결과를 JSON으로 돌려준다."""
    since = timezone.localdate() - timedelta(days=6)
    logs = list(
        MoodLog.objects.filter(user=request.user, date__gte=since).order_by('date')
    )
    # 기록이 너무 적으면 AI를 부르지 않고 안내만 한다 (비용 절약 + 의미 없는 리포트 방지)
    if len(logs) < MIN_LOGS:
        return JsonResponse({
            'error': f'리포트를 만들려면 최근 7일 중 {MIN_LOGS}일 이상의 기록이 필요해요. '
                     f'(지금은 {len(logs)}일)'
        }, status=400)
    try:
        report = generate_report(logs)
    except AIReportError:
        # 자세한 원인은 ai.py에서 이미 서버 로그에 남겼다. 화면에는 고정 문구만 보낸다.
        return JsonResponse({'error': FRIENDLY_ERROR}, status=502)
    except Exception:
        # 예상하지 못한 오류가 나도 앱이 죽지 않게 마지막으로 한 번 더 막는다
        logger.exception('AI 리포트 처리 중 예상치 못한 오류')
        return JsonResponse({'error': FRIENDLY_ERROR}, status=502)
    return JsonResponse({'report': report})


@login_required
def log_create(request):
    if request.method == 'POST':
        form = MoodLogForm(request.POST, user=request.user)
        if form.is_valid():
            log = form.save(commit=False)
            log.user = request.user
            try:
                log.save()
            except IntegrityError:
                # 저장 버튼을 거의 동시에 두 번 눌러 같은 날짜가 먼저 저장된 경우
                form.add_error('date', '이 날짜에는 이미 기록이 있어요. 목록에서 수정해 주세요.')
            else:
                messages.success(request, '기록을 저장했어요.')
                return redirect('log_list')
    else:
        form = MoodLogForm(user=request.user, initial={'date': timezone.localdate()})
    return render(request, 'diary/log_form.html', {'form': form, 'title': '기분 기록하기'})


@login_required
def log_update(request, pk):
    # user=request.user 조건 덕분에 남의 기록은 404가 된다
    log = get_object_or_404(MoodLog, pk=pk, user=request.user)
    if request.method == 'POST':
        form = MoodLogForm(request.POST, instance=log, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '기록을 수정했어요.')
            return redirect('log_list')
    else:
        form = MoodLogForm(instance=log, user=request.user)
    return render(request, 'diary/log_form.html', {'form': form, 'title': '기록 수정'})


@login_required
def log_delete(request, pk):
    log = get_object_or_404(MoodLog, pk=pk, user=request.user)
    if request.method == 'POST':
        log.delete()
        messages.success(request, '기록을 삭제했어요.')
        return redirect('log_list')
    return render(request, 'diary/log_confirm_delete.html', {'log': log})
