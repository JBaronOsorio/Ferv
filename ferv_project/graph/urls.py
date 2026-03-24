from django.urls import path
from . import views

app_name = 'graph'

urlpatterns = [
    path('', views.index, name='index'),
    path('welcome/', views.welcome, name='welcome'),
]