"""
Tests for user authentication and registration.

HU06: User Registration
- Happy path: successful registration
- Alternative: duplicate email validation
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import response

User = get_user_model()


@pytest.mark.django_db
class TestUserRegistration:
    """Tests for user registration endpoint (POST /user/register/)."""

    def test_registration_successful(self, client):
        """
        HU06 — Happy Path: User registers successfully.
        
        Given: Registration form with valid data
        When: POST to /user/register/
        Then: User is created, logged in, and redirected to profile_setup
        """
        url = reverse('user:register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        
        response = client.post(url, data, follow=True)
        
        # User should be created
        user = User.objects.get(username='newuser')
        assert user is not None
        assert user.email == 'newuser@example.com'
        assert not user.profile_completed
        
        # Should be logged in and redirected to profile_setup
        assert response.status_code == 200
        assert response.wsgi_request.user.is_authenticated
        assert response.wsgi_request.user.username == 'newuser'

    def test_registration_duplicate_email(self, client, test_user):
        """
        HU06 — Alternative: Reject registration with duplicate email.
        
        Given: User already exists with email 'testuser@example.com'
        When: POST to /user/register/ with same email
        Then: Form shows validation error, user not created
        """
        url = reverse('user:register')
        data = {
            'username': 'differentuser',
            'email': test_user.email,  # Duplicate email
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        
        response = client.post(url, data)
        
        # Should not redirect (form re-rendered with errors)
        assert response.status_code == 200
        assert 'Este correo ya está registrado.' in response.content.decode('utf-8')


        # No new user created
        assert not User.objects.filter(username='differentuser').exists()

    def test_registration_password_mismatch(self, client):
        """
        HU06 — Alternative: Reject registration with mismatched passwords.
        
        Given: Registration form with non-matching password fields
        When: POST to /user/register/
        Then: Form shows validation error, user not created
        """
        url = reverse('user:register')
        data = {
            'username': 'newuser2',
            'email': 'newuser2@example.com',
            'password1': 'SecurePass123!',
            'password2': 'DifferentPass123!',
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        assert not User.objects.filter(username='newuser2').exists()

    def test_registration_authenticated_user_redirect(self, client, test_user_with_profile):
        """
        HU06 — Alternative: Authenticated user should be redirected away from register.
        
        Given: An authenticated user visits /user/register/
        When: GET to /user/register/
        Then: Redirect to graph:map
        """
        client.force_login(test_user_with_profile)
        url = reverse('user:register')
        
        response = client.get(url)
        
        assert response.status_code == 302
        assert response.url == reverse('graph:map')
