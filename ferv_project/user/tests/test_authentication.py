"""
Tests for user login and authentication flows.

HU07: Protected Routes and Session Management
- Happy path: authenticated access to protected route
- Alternative: redirect unauthenticated user to login
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestAuthenticatedAccess:
    """Tests for protected routes requiring authentication."""

    def test_map_view_authenticated(self, client, test_user_with_profile):
        """
        HU07 — Happy Path: Authenticated user can access map.
        
        Given: Authenticated user with completed profile
        When: GET /graph/map/
        Then: Return 200 with map template
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:map')
        
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'graph/map.html' in [t.name for t in response.templates]

    def test_map_view_unauthenticated(self, client):
        """
        HU07 — Alternative: Unauthenticated user is redirected to login.
        
        Given: Anonymous user
        When: GET /graph/map/
        Then: Redirect to /user/ (login page)
        """
        url = reverse('graph:map')
        response = client.get(url)
        
        assert response.status_code == 302

    def test_welcome_view_authenticated(self, client, test_user_with_profile):
        """
        HU07 — Happy Path: Authenticated user can access welcome page.
        
        Given: Authenticated user with completed profile
        When: GET /graph/welcome/
        Then: Return 200 with welcome template
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:welcome')
        
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'graph/welcome.html' in [t.name for t in response.templates]

    def test_welcome_view_unauthenticated(self, client):
        """
        HU07 — Alternative: Unauthenticated user cannot access welcome.
        
        Given: Anonymous user
        When: GET /graph/welcome/
        Then: Redirect to login
        """
        url = reverse('graph:welcome')
        response = client.get(url)
        
        assert response.status_code == 302

    def test_login_flow(self, client, test_user_with_profile):
        """
        HU07 — Happy Path: User can log in successfully.
        
        Given: Registered user
        When: POST to /user/ with username and password
        Then: User is authenticated and redirected to map
        """
        url = reverse('user:login')
        data = {
            'username': test_user_with_profile.username,
            'password': 'TestPass123!',
        }
        
        response = client.post(url, data, follow=True)
        
        assert response.status_code == 200
        assert response.wsgi_request.user.is_authenticated
        assert response.wsgi_request.user.username == test_user_with_profile.username

    def test_login_redirect_incomplete_profile(self, client, test_user):
        """
        HU07 — Alternative: User with incomplete profile redirected to setup.
        
        Given: User exists but profile_completed=False
        When: POST to /user/ with valid credentials
        Then: Redirect to /user/profile-setup/
        """
        url = reverse('user:login')
        data = {
            'username': test_user.username,
            'password': 'TestPass123!',
        }
        
        response = client.post(url, data, follow=True)
        
        assert response.status_code == 200
        assert response.wsgi_request.user.is_authenticated
        # Check if we're on profile setup page
        assert 'profile' in response.wsgi_request.path

    def test_login_invalid_credentials(self, client):
        """
        HU07 — Alternative: Invalid credentials show error.
        
        Given: Login form with wrong password
        When: POST to /user/
        Then: Form is re-rendered with error message
        """
        url = reverse('user:login')
        data = {
            'username': 'nonexistent',
            'password': 'WrongPassword',
        }
        
        response = client.post(url, data)
        
        assert response.status_code == 200
        assert not response.wsgi_request.user.is_authenticated

    def test_logout_flow(self, client, test_user_with_profile):
        """
        HU07 — Happy Path: User can log out.
        
        Given: Authenticated user
        When: POST to /user/logout/
        Then: User is logged out and redirected to login
        """
        client.force_login(test_user_with_profile)
        url = reverse('user:logout')
        
        response = client.post(url, follow=True)
        
        assert response.status_code == 200
        assert not response.wsgi_request.user.is_authenticated
