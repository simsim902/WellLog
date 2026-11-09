from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .ai import FRIENDLY_ERROR
from .models import MoodLog


class DiaryTests(TestCase):
    def setUp(self):
        self.me = User.objects.create_user('me', password='pw12345!')
        self.other = User.objects.create_user('other', password='pw12345!')

    def test_login_required(self):
        r = self.client.get(reverse('log_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r.url)

    def test_signup_logs_in(self):
        r = self.client.post(reverse('signup'), {
            'username': 'newbie', 'password1': 'Str0ng-pass-99', 'password2': 'Str0ng-pass-99'})
        self.assertRedirects(r, reverse('log_list'))
        self.assertTrue(User.objects.filter(username='newbie').exists())

    def test_one_log_per_day(self):
        self.client.login(username='me', password='pw12345!')
        data = {'date': '2026-11-01', 'score': 3, 'memo': 'a'}
        self.client.post(reverse('log_create'), data)
        r = self.client.post(reverse('log_create'), data)
        self.assertEqual(r.status_code, 200)  # 에러와 함께 폼 다시 표시
        self.assertEqual(MoodLog.objects.filter(user=self.me).count(), 1)

    def test_only_own_logs(self):
        theirs = MoodLog.objects.create(user=self.other, date=date(2026, 11, 1), score=5)
        self.client.login(username='me', password='pw12345!')
        self.assertNotIn(theirs, self.client.get(reverse('log_list')).context['logs'])
        self.assertEqual(self.client.get(reverse('log_update', args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('log_delete', args=[theirs.pk])).status_code, 404)
        self.assertTrue(MoodLog.objects.filter(pk=theirs.pk).exists())

    def test_edit_and_delete(self):
        log = MoodLog.objects.create(user=self.me, date=date(2026, 11, 1), score=2)
        self.client.login(username='me', password='pw12345!')
        self.client.post(reverse('log_update', args=[log.pk]),
                         {'date': '2026-11-01', 'score': 4, 'memo': 'better'})
        log.refresh_from_db()
        self.assertEqual(log.score, 4)
        self.client.post(reverse('log_delete', args=[log.pk]))
        self.assertFalse(MoodLog.objects.filter(pk=log.pk).exists())

    def test_stats_page(self):
        MoodLog.objects.create(user=self.me, date=date(2026, 11, 3), score=4)
        MoodLog.objects.create(user=self.other, date=date(2026, 11, 4), score=1)
        self.client.login(username='me', password='pw12345!')
        r = self.client.get(reverse('stats'), {'month': '2026-11'})
        self.assertEqual(r.status_code, 200)
        cells = [c for w in r.context['weeks'] for c in w if c['log']]
        self.assertEqual([c['date'] for c in cells], [date(2026, 11, 3)])  # 본인 기록만
        self.assertEqual(len(r.context['chart']['scores']), 7)
        # 잘못된 month 값이어도 오류 없이 이번 달 표시
        self.assertEqual(self.client.get(reverse('stats'), {'month': 'abc'}).status_code, 200)

    def test_ai_report_flow(self):
        from datetime import timedelta
        from unittest import mock

        from django.utils import timezone

        from .ai import AIReportError

        url = reverse('ai_report')
        self.assertEqual(self.client.post(url).status_code, 302)  # 로그인 필요
        self.client.login(username='me', password='pw12345!')
        self.assertEqual(self.client.get(url).status_code, 405)   # POST만 허용
        self.assertEqual(self.client.post(url).status_code, 400)  # 기록 없음

        today = timezone.localdate()
        for i, memo in enumerate(['피곤함', '보통', '좋음']):
            MoodLog.objects.create(user=self.me, date=today - timedelta(days=i), score=2, memo=memo)
        MoodLog.objects.create(user=self.me, date=today - timedelta(days=10), score=5)  # 범위 밖
        MoodLog.objects.create(user=self.other, date=today, score=1, memo='남의 메모')

        with mock.patch('diary.views.generate_report', return_value='요약과 조언') as fake:
            r = self.client.post(url)
        self.assertEqual(r.json(), {'report': '요약과 조언'})
        sent = fake.call_args[0][0]
        self.assertEqual(sorted(l.memo for l in sent), ['보통', '좋음', '피곤함'])  # 본인 + 최근 7일만 전달

        with mock.patch('diary.views.generate_report', side_effect=AIReportError('실패')):
            r = self.client.post(url)
        self.assertEqual((r.status_code, r.json()['error']), (502, FRIENDLY_ERROR))

    # ---------- AI 실패 처리 ----------
    def _make_week_logs(self, n=3):
        from datetime import timedelta

        from django.utils import timezone
        today = timezone.localdate()
        for i in range(n):
            MoodLog.objects.create(user=self.me, date=today - timedelta(days=i), score=3, memo=f'메모{i}')

    def test_ai_too_few_logs_skips_api(self):
        from unittest import mock
        self._login()
        self._make_week_logs(2)
        with mock.patch('diary.ai.genai.Client') as client:
            r = self.client.post(reverse('ai_report'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('3일 이상', r.json()['error'])
        client.assert_not_called()  # 기록이 적으면 AI를 아예 부르지 않는다

    def test_ai_failures_show_friendly_message_and_log_details(self):
        from unittest import mock
        self._login()
        self._make_week_logs(3)
        secret = 'SECRET-INTERNAL-DETAIL-12345'
        failures = {
            '잘못된 키/서버 오류': Exception(f'API key not valid {secret}'),
            '인터넷 끊김': ConnectionError(secret),
            '시간 초과': TimeoutError(secret),
        }
        for name, exc in failures.items():
            with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'fake'}), \
                 mock.patch('diary.ai.genai.Client') as client, \
                 self.assertLogs('diary.ai', level='ERROR') as logs:
                client.return_value.models.generate_content.side_effect = exc
                r = self.client.post(reverse('ai_report'))
            self.assertEqual(r.status_code, 502, name)
            self.assertEqual(r.json(), {'error': FRIENDLY_ERROR}, name)
            self.assertNotIn(secret, r.content.decode(), name)             # 화면엔 에러 내용이 없다
            self.assertIn(secret, '\n'.join(logs.output), name)            # 서버 로그엔 남는다

    def test_ai_empty_response_and_missing_key(self):
        from unittest import mock
        self._login()
        self._make_week_logs(3)
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'fake'}), \
             mock.patch('diary.ai.genai.Client') as client, \
             self.assertLogs('diary.ai', level='ERROR'):
            client.return_value.models.generate_content.return_value.text = '  '
            r = self.client.post(reverse('ai_report'))
        self.assertEqual((r.status_code, r.json()), (502, {'error': FRIENDLY_ERROR}))

        with mock.patch.dict('os.environ', {}, clear=True), self.assertLogs('diary.ai', level='ERROR'):
            r = self.client.post(reverse('ai_report'))
        self.assertEqual((r.status_code, r.json()), (502, {'error': FRIENDLY_ERROR}))

    def test_ai_unexpected_error_in_view_is_caught(self):
        from unittest import mock
        self._login()
        self._make_week_logs(3)
        with mock.patch('diary.views.generate_report', side_effect=RuntimeError('boom')), \
             self.assertLogs('diary.views', level='ERROR'):
            r = self.client.post(reverse('ai_report'))
        self.assertEqual((r.status_code, r.json()), (502, {'error': FRIENDLY_ERROR}))

    def test_ai_timeout_is_configured(self):
        from unittest import mock
        self._make_week_logs(3)
        from .ai import TIMEOUT_MS, generate_report
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'fake'}), \
             mock.patch('diary.ai.genai.Client') as client:
            client.return_value.models.generate_content.return_value.text = '리포트'
            self.assertEqual(generate_report(list(MoodLog.objects.all())), '리포트')
        http_options = client.call_args.kwargs['http_options']
        self.assertEqual(http_options.timeout, TIMEOUT_MS)
        self.assertLessEqual(TIMEOUT_MS, 20_000)

    def test_ai_missing_key(self):
        from unittest import mock

        from .ai import AIReportError, generate_report

        with mock.patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(AIReportError):
                generate_report([])

    # ---------- 오류 점검 ----------
    def _login(self):
        self.client.login(username='me', password='pw12345!')

    def test_duplicate_date_shows_message_not_error(self):
        self._login()
        data = {'date': '2026-11-01', 'score': 3, 'memo': ''}
        self.client.post(reverse('log_create'), data)
        r = self.client.post(reverse('log_create'), data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '이미 기록이 있어요')

    def test_blank_memo_is_saved(self):
        self._login()
        r = self.client.post(reverse('log_create'), {'date': '2026-11-01', 'score': 3, 'memo': ''})
        self.assertRedirects(r, reverse('log_list'))
        self.assertEqual(MoodLog.objects.get(user=self.me).memo, '')

    def test_bad_input_never_500(self):
        self._login()
        bad = [
            {'date': '2026-11-01', 'score': '99', 'memo': ''},
            {'date': '2026-11-01', 'score': '0', 'memo': ''},
            {'date': '2026-11-01', 'score': 'abc', 'memo': ''},
            {'date': '2026-11-01', 'memo': ''},                   # 점수 없음
            {'date': 'abc', 'score': '3', 'memo': ''},
            {'date': '2026-02-30', 'score': '3', 'memo': ''},     # 없는 날짜
            {'date': '0001-01-01', 'score': '3', 'memo': ''},
            {'date': '9999-12-31', 'score': '3', 'memo': ''},
            {},
        ]
        for data in bad:
            r = self.client.post(reverse('log_create'), data)
            self.assertIn(r.status_code, (200, 302), data)  # 500이 아니면 OK
        # 잘못된 입력 6개는 저장되지 않고, 올바른 날짜인 0001-01-01 / 9999-12-31 두 개만 저장된다
        self.assertEqual(
            sorted(MoodLog.objects.filter(user=self.me).values_list('date', flat=True)),
            [date(1, 1, 1), date(9999, 12, 31)],
        )

    def test_other_users_logs_are_private(self):
        theirs = MoodLog.objects.create(user=self.other, date=date(2026, 11, 1), score=5, memo='비밀')
        self._login()
        for name in ('log_update', 'log_delete'):
            url = reverse(name, args=[theirs.pk])
            self.assertEqual(self.client.get(url).status_code, 404, name)
            self.assertEqual(self.client.post(url, {'date': '2026-11-01', 'score': 1, 'memo': 'x'}).status_code, 404, name)
        theirs.refresh_from_db()
        self.assertEqual((theirs.score, theirs.memo), (5, '비밀'))
        self.assertNotContains(self.client.get(reverse('log_list')), '비밀')

    def test_anonymous_redirected_to_login(self):
        for name, args in [('stats', []), ('log_list', []), ('log_create', []),
                           ('log_update', [1]), ('log_delete', [1])]:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn('/accounts/login/', r.url, name)

    def test_stats_empty_account(self):
        self._login()
        r = self.client.get(reverse('stats'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '아직 기록이 없어요')

    def test_chartjs_is_served_locally(self):
        from django.contrib.staticfiles import finders
        self._login()
        MoodLog.objects.create(user=self.me, date=date(2026, 11, 1), score=3)
        html = self.client.get(reverse('stats')).content.decode()
        self.assertIn('/static/diary/vendor/chart.umd.min.js', html)
        self.assertNotIn('cdn.jsdelivr.net', html)            # 외부 CDN을 쓰지 않는다
        self.assertTrue(finders.find('diary/vendor/chart.umd.min.js'))  # 파일이 실제로 존재한다

    def test_stats_extreme_month_values(self):
        self._login()
        for m in ['abc', '2026-13', '0001-01', '9999-12', '10000-01', '-5-3', '2026-11-05', '', '1899-12', '2101-01']:
            self.assertEqual(self.client.get(reverse('stats'), {'month': m}).status_code, 200, m)

    def test_logout(self):
        self.client.login(username='me', password='pw12345!')
        r = self.client.post(reverse('logout'))
        self.assertRedirects(r, reverse('login'))
