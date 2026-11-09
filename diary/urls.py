from django.urls import path

from . import views

urlpatterns = [
    path('', views.log_list, name='log_list'),
    path('stats/', views.stats, name='stats'),
    path('report/', views.ai_report, name='ai_report'),
    path('new/', views.log_create, name='log_create'),
    path('<int:pk>/edit/', views.log_update, name='log_update'),
    path('<int:pk>/delete/', views.log_delete, name='log_delete'),
]
