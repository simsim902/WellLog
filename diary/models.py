from django.conf import settings
from django.db import models


class MoodLog(models.Model):
    SCORE_CHOICES = [
        (1, '1 - 매우 나쁨'),
        (2, '2 - 나쁨'),
        (3, '3 - 보통'),
        (4, '4 - 좋음'),
        (5, '5 - 매우 좋음'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    score = models.PositiveSmallIntegerField(choices=SCORE_CHOICES)
    memo = models.TextField(blank=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f'{self.user} {self.date} ({self.score})'
