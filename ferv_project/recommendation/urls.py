from django.urls import path

from recommendation import views

app_name = 'recommendation'

urlpatterns = [
    path('recommend/', views.recommend, name='recommend'),
    path('node_based/', views.node_based_recommend, name='node_based'),
    path('exploratory/', views.exploratory_recommend, name='exploratory'),
]
