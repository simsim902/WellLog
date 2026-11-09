from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import MoodLog


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username',)


class MoodLogForm(forms.ModelForm):
    class Meta:
        model = MoodLog
        fields = ('date', 'score', 'memo')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'memo': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_date(self):
        date = self.cleaned_data['date']
        # 하루 1개 제한: 같은 사용자 + 같은 날짜 기록이 이미 있으면 에러
        # (수정 중인 기록 자신은 제외)
        exists = MoodLog.objects.filter(user=self.user, date=date)
        if self.instance.pk:
            exists = exists.exclude(pk=self.instance.pk)
        if exists.exists():
            raise forms.ValidationError('이 날짜에는 이미 기록이 있어요. 목록에서 수정해 주세요.')
        return date
