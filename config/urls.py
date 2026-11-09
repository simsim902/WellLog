from django.contrib import admin
from django.urls import include, path

from diary import views as diary_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # 로그인/로그아웃/비밀번호 관련 Django 기본 인증 URL (login, logout 등)
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/signup/', diary_views.signup, name='signup'),
    path('', include('diary.urls')),
]
