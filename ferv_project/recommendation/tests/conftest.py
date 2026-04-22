"""
conftest.py
-----------
Pytest configuration for the recommendation app.
App-specific fixtures can be added here.
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_gemini_response():
    """Mock response from Gemini API."""
    return {
        'recommendations': [
            {
                'place_id': 'mock_place_001',
                'name': 'Café Literario',
                'rationale': 'Matches your quiet atmosphere preference',
                'confidence': 0.95,
            },
            {
                'place_id': 'mock_place_002',
                'name': 'Biblioteca Distrital',
                'rationale': 'Perfect for reading activities',
                'confidence': 0.87,
            },
        ]
    }
