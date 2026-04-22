"""
Tests for user profile setup and editing.

HU05: User Profile Setup
- Happy path: complete profile setup
- Alternative: save without selecting any preferences
- Alternative: edit existing profile
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestProfileSetup:
    """Tests for user profile setup endpoint (GET/POST /user/profile-setup/)."""

    def test_profile_setup_successful(self, client, test_user, complete_profile_data):
        """
        HU05 — Happy Path: User completes profile setup successfully.
        
        Given: Test user not yet profiled, logged in
        When: POST to /user/profile-setup/ with complete preferences
        Then: profile_completed=True, redirected to graph:map
        """
        client.force_login(test_user)
        url = reverse('user:profile_setup')
        
        response = client.post(url, complete_profile_data, follow=True)
        
        # User profile should be updated
        test_user.refresh_from_db()
        assert test_user.profile_completed is True
        assert test_user.preferred_place_types == ['cafe', 'bar', 'restaurant']
        assert test_user.preferred_atmospheres == ['quiet', 'intimate']
        assert test_user.preferred_activities == ['reading', 'socializing', 'gastronomy']
        assert test_user.budget_range == 'medium'
        
        # Should redirect to map
        assert response.status_code == 200
        final_url = response.wsgi_request.path
        assert 'map' in final_url

    
    def test_profile_setup_minimal_preferences(self, client, test_user, minimal_profile_data):
        """
        HU05 — Alternative: User can save profile with minimal preferences (one per field).

        Given: Test user not yet profiled, logged in
        When: POST to /user/profile-setup/ with one selection per field
        Then: profile_completed=True
        """
        client.force_login(test_user)
        url = reverse('user:profile_setup')
        response = client.post(url, minimal_profile_data, follow=True)
        test_user.refresh_from_db()
        assert test_user.profile_completed is True
    

    def test_profile_setup_already_completed_redirect(self, client, test_user_with_profile):
        """
        HU05 — Alternative: User with completed profile should be redirected.
        
        Given: An authenticated user with profile_completed=True
        When: GET to /user/profile-setup/
        Then: Redirect to graph:map (skip questionnaire)
        """
        client.force_login(test_user_with_profile)
        url = reverse('user:profile_setup')
        
        response = client.get(url)
        
        assert response.status_code == 302
        assert response.url == reverse('graph:map')

    def test_profile_setup_requires_login(self, client):
        """
        HU07 — Alternative: Unauthenticated user cannot access profile setup.
        
        Given: Anonymous user
        When: GET to /user/profile-setup/
        Then: Redirect to login page
        """
        url = reverse('user:profile_setup')
        response = client.get(url)
        
        assert response.status_code == 302


@pytest.mark.django_db
class TestProfileEdit:
    """Tests for user profile editing endpoint (POST /user/profile/edit/)."""

    def test_profile_edit_successful(self, client, test_user_with_profile, complete_profile_data):
        """
        HU05 — Happy Path: User edits existing profile.
        
        Given: Authenticated user with completed profile
        When: POST to /user/profile/edit/ with new preferences
        Then: Preferences updated, redirected to user:profile
        """
        client.force_login(test_user_with_profile)
        url = reverse('user:profile_edit')
        
        # Modify preferences
        new_data = {
            'preferred_place_types': ['park', 'gallery'],
            'preferred_atmospheres': ['lively', 'family'],
            'preferred_activities': ['art', 'nature'],
            'budget_range': 'high',
        }
        
        response = client.post(url, new_data, follow=True)
        
        test_user_with_profile.refresh_from_db()
        assert test_user_with_profile.preferred_place_types == ['park', 'gallery']
        assert test_user_with_profile.preferred_atmospheres == ['lively', 'family']
        assert test_user_with_profile.budget_range == 'high'
        assert test_user_with_profile.profile_completed is True

    def test_profile_edit_requires_login(self, client):
        """
        HU07 — Alternative: Unauthenticated user cannot edit profile.
        
        Given: Anonymous user
        When: GET to /user/profile/edit/
        Then: Redirect to login page
        """
        url = reverse('user:profile_edit')
        response = client.get(url)
        
        assert response.status_code == 302

    def test_profile_view_requires_login(self, client):
        """
        HU07 — Alternative: Unauthenticated user cannot view profile.
        
        Given: Anonymous user
        When: GET to /user/profile/
        Then: Redirect to login page
        """
        url = reverse('user:profile')
        response = client.get(url)
        
        assert response.status_code == 302
