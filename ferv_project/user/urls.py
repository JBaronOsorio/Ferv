from django.urls import path
from . import views

app_name = 'user'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('profile-setup/', views.profile_setup_view, name='profile_setup'),
    path('', views.login_view, name='login'), # Set the login view as the default path
    path('logout/', views.logout_view, name='logout'),
]
