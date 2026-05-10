from django.urls import path

from recommendation import views

app_name = 'recommendation'

urlpatterns = [
    path('recommend/', views.recommend, name='recommend'),
    path('exploratory/', views.exploratory_recommend, name='exploratory'),
]
