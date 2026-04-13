from django.urls import path
from graph import views

app_name = 'graph'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/', views.GraphAPIView.as_view(), name='graph-api'),
    path('welcome/', views.welcome, name='welcome'),
]