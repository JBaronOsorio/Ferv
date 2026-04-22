"""
conftest.py
-----------
Pytest configuration for the user app.
App-specific fixtures can be added here.
"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_credentials():
    """Standard credentials for test user."""
    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'TestPass123!',
    }
