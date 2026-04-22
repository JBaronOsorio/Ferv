"""
Tests for recommendation service and chat.

HU02: Recommendation Chat
- Happy path: successful recommendation with mocked Gemini
- Alternative: Gemini API error handling with mocked exception
- Note: Both tests marked with @skip until chat endpoint is fully implemented
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.contrib.auth import get_user_model
from graph.models import GraphNode

User = get_user_model()


@pytest.mark.skip(reason="Endpoint pendiente de implementar — HU02")
@pytest.mark.django_db
class TestRecommendationChat:
    """Tests for recommendation chat endpoint (POST /api/recommendation/recommend/)."""

    @patch('recommendation.llm_client.GeminiClient.generate_recommendations')
    def test_recommend_successful(self, mock_gemini, client, test_user_with_profile):
        """
        HU02 — Happy Path: Chat returns recommendations successfully.
        
        Given: Authenticated user, Gemini API responds successfully
        When: POST /api/recommendation/recommend/ with prompt
        Then: Return list of recommended nodes with rationale
        """
        client.force_login(test_user_with_profile)
        
        # Mock Gemini response
        mock_gemini.return_value = {
            'recommendations': [
                {'place_id': 'place_001', 'rationale': 'Matches your vibe'},
                {'place_id': 'place_002', 'rationale': 'Great coffee'},
            ]
        }
        
        url = reverse('recommendation:recommend')
        data = json.dumps({'prompt': 'Find me a quiet cafe'})
        
        response = client.post(
            url,
            data=data,
            content_type='application/json',
        )
        
        assert response.status_code == 200
        response_data = json.loads(response.content)
        
        # Verify recommendations returned
        assert 'recommendations' in response_data
        assert len(response_data['recommendations']) == 2
        
        # Verify Gemini was called with user profile
        mock_gemini.assert_called_once()
        call_args = mock_gemini.call_args
        assert test_user_with_profile.get_profile_as_prompt_text() in str(call_args)

    @patch('recommendation.llm_client.GeminiClient.generate_recommendations')
    def test_recommend_empty_prompt(self, mock_gemini, client, test_user_with_profile):
        """
        HU02 — Alternative: Empty prompt rejected.
        
        Given: POST with empty or missing prompt field
        When: POST /api/recommendation/recommend/ with empty prompt
        Then: Return 400 with error message
        """
        client.force_login(test_user_with_profile)
        
        url = reverse('recommendation:recommend')
        data = json.dumps({'prompt': ''})
        
        response = client.post(
            url,
            data=data,
            content_type='application/json',
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.content)
        assert 'error' in response_data
        mock_gemini.assert_not_called()

    @patch('recommendation.llm_client.GeminiClient.generate_recommendations')
    def test_recommend_gemini_error(self, mock_gemini, client, test_user_with_profile):
        """
        HU02 — Alternative: Gemini API error is caught and returned gracefully.
        
        Given: Gemini API throws an exception
        When: POST /api/recommendation/recommend/ with prompt
        Then: Return 500 with error message (not crash)
        """
        client.force_login(test_user_with_profile)
        
        # Mock Gemini to throw exception
        mock_gemini.side_effect = Exception('Gemini API unavailable')
        
        url = reverse('recommendation:recommend')
        data = json.dumps({'prompt': 'Find me a quiet cafe'})
        
        response = client.post(
            url,
            data=data,
            content_type='application/json',
        )
        
        assert response.status_code == 500
        response_data = json.loads(response.content)
        assert 'error' in response_data

    def test_recommend_requires_authentication(self, client):
        """
        HU07 — Alternative: Unauthenticated user cannot get recommendations.
        
        Given: Anonymous user
        When: POST /api/recommendation/recommend/
        Then: Redirect to login
        """
        url = reverse('recommendation:recommend')
        response = client.post(url, {})
        
        assert response.status_code == 302
        assert 'login' in response.url

    @patch('recommendation.llm_client.GeminiClient.generate_recommendations')
    def test_recommend_invalid_json(self, mock_gemini, client, test_user_with_profile):
        """
        HU02 — Alternative: Invalid JSON returns 400.
        
        Given: POST with malformed JSON
        When: POST /api/recommendation/recommend/
        Then: Return 400 with error message
        """
        client.force_login(test_user_with_profile)
        
        url = reverse('recommendation:recommend')
        response = client.post(
            url,
            data='invalid json',
            content_type='application/json',
        )
        
        assert response.status_code == 400
        mock_gemini.assert_not_called()


@pytest.mark.skip(reason="Endpoint pendiente de implementar — HU02")
@pytest.mark.django_db
class TestOneShotRecommendation:
    """Tests for legacy one-shot recommendation endpoint."""

    @patch('recommendation.recommendation_service.RecommendationService.recommend_one_shot')
    def test_one_shot_recommendation_success(self, mock_service, client, test_user_with_profile):
        """
        HU02 — Happy Path: One-shot recommendation returns results.
        
        Given: Authenticated user, valid query string
        When: GET /graph/api/one_shot_recommendation/<query>
        Then: Return top recommendations
        """
        client.force_login(test_user_with_profile)
        
        # Mock service
        mock_service.return_value = []
        
        url = reverse(
            'graph:one-shot-recommendation',
            kwargs={'query': 'quiet cafes'}
        )
        
        response = client.get(url)
        
        assert response.status_code == 200
        response_data = json.loads(response.content)
        assert 'query' in response_data
        assert 'results' in response_data

    @patch('recommendation.recommendation_service.RecommendationService.recommend_one_shot')
    def test_one_shot_recommendation_service_error(self, mock_service, client, test_user_with_profile):
        """
        HU02 — Alternative: Service error returns 500.
        
        Given: Recommendation service throws exception
        When: GET /graph/api/one_shot_recommendation/<query>
        Then: Return 500 error
        """
        client.force_login(test_user_with_profile)
        
        mock_service.side_effect = Exception('Service error')
        
        url = reverse(
            'graph:one-shot-recommendation',
            kwargs={'query': 'quiet cafes'}
        )
        
        response = client.get(url)
        
        assert response.status_code == 500
        response_data = json.loads(response.content)
        assert 'error' in response_data
