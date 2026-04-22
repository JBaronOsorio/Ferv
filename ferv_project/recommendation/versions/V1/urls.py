from django.urls import path
from recommendation.views import RecommendationView

app_name = 'recommendation'

urlpatterns = [
    path('', RecommendationView.as_view(), name='recommend'),
]