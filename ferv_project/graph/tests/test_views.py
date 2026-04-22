"""
Tests for graph map views.

HU07: Protected Routes
- Tests for map view authentication
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestMapViews:
    """Tests for map-related views."""

    def test_map_view_renders_template(self, client, test_user_with_profile):
        """
        HU07 — Happy Path: Map view renders correctly for authenticated user.
        
        Given: Authenticated user
        When: GET /graph/map/
        Then: Render map.html template
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:map')
        
        response = client.get(url)
        
        assert response.status_code == 200
        templates = [t.name for t in response.templates]
        assert 'graph/map.html' in templates

    def test_index_view(self, client):
        """
        Graph index view should be publicly accessible.
        
        Given: Anonymous user
        When: GET /graph/
        Then: Render index.html template
        """
        url = reverse('graph:index')
        
        response = client.get(url)
        
        assert response.status_code == 200
        templates = [t.name for t in response.templates]
        assert 'graph/index.html' in templates

    def test_welcome_view_renders_template(self, client, test_user_with_profile):
        """
        HU07 — Happy Path: Welcome view renders featured places.
        
        Given: Authenticated user
        When: GET /graph/welcome/
        Then: Render welcome.html with featured_places context
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:welcome')
        
        response = client.get(url)
        
        assert response.status_code == 200
        templates = [t.name for t in response.templates]
        assert 'graph/welcome.html' in templates
