"""
conftest.py
-----------
Pytest configuration and shared fixtures for the Ferv project.
Centralizes setup/teardown, database fixtures, and authentication helpers.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from places.models import Place
from graph.models import GraphNode, GraphEdge

# Import Django settings
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ferv_project.settings')
django.setup()

User = get_user_model()


# ============================================================================
# FIXTURES: User/Authentication
# ============================================================================

@pytest.fixture
def user_data():
    """Standard test user data."""
    return {
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'TestPass123!',
        'password1': 'TestPass123!',
        'password2': 'TestPass123!',
    }


@pytest.fixture
def test_user(user_data, db):
    """Create and return a test user with profile_completed=False."""
    user = User.objects.create_user(
        username=user_data['username'],
        email=user_data['email'],
        password=user_data['password'],
        profile_completed=False,
    )
    return user


@pytest.fixture
def test_user_with_profile(user_data, db):
    """Create and return a test user with completed profile."""
    user = User.objects.create_user(
        username='profileuser',
        email='profileuser@example.com',
        password='TestPass123!',
        profile_completed=True,
        preferred_place_types=['bar', 'cafe'],
        preferred_atmospheres=['quiet', 'intimate'],
        preferred_activities=['reading', 'socializing'],
        budget_range='medium',
    )
    return user


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def authenticated_client(client, test_user_with_profile):
    """Django test client with authenticated user."""
    client.force_login(test_user_with_profile)
    return client


# ============================================================================
# FIXTURES: Places
# ============================================================================

@pytest.fixture
def test_place(db):
    """Create and return a test place."""
    return Place.objects.create(
        place_id='test_place_001',
        name='Café Azul',
        address='Carrera 5 #123, Bogotá',
        neighborhood='La Candelaria',
        latitude=4.7110,
        longitude=-74.0721,
        rating=4.5,
        price_level=2,
        review_count=42,
        editorial_summary='Acogedor café tradicional en el corazón de Bogotá.',
    )


@pytest.fixture
def test_place_2(db):
    """Create and return a second test place."""
    return Place.objects.create(
        place_id='test_place_002',
        name='Parque Bolívar',
        address='Calle 7 #9, Bogotá',
        neighborhood='Centro',
        latitude=4.7130,
        longitude=-74.0700,
        rating=4.2,
        price_level=1,
        review_count=156,
        editorial_summary='Icónico parque urbano con vista a la Catedral.',
    )


# ============================================================================
# FIXTURES: Graph Nodes and Edges
# ============================================================================

@pytest.fixture
def test_graph_node(db, test_user_with_profile, test_place):
    """Create and return a test graph node."""
    return GraphNode.objects.create(
        user=test_user_with_profile,
        place=test_place,
        rationale='Recomendado por tu perfil',
        status='in_graph',
        is_favorite=False,
    )


@pytest.fixture
def test_graph_edge(db, test_user_with_profile, test_graph_node, test_place_2):
    """Create and return a test graph edge."""
    node_2 = GraphNode.objects.create(
        user=test_user_with_profile,
        place=test_place_2,
        rationale='Lugar relacionado',
        status='in_graph',
        is_favorite=False,
    )
    return GraphEdge.objects.create(
        user=test_user_with_profile,
        from_node=test_graph_node,
        to_node=node_2,
        weight=0.8,
        reason='proximity',
        reason_type='spatial',
    )


# ============================================================================
# FIXTURES: Profile Data
# ============================================================================

@pytest.fixture
def complete_profile_data():
    """Complete profile setup form data."""
    return {
        'preferred_place_types': ['cafe', 'bar', 'restaurant'],
        'preferred_atmospheres': ['quiet', 'intimate'],
        'preferred_activities': ['reading', 'socializing', 'gastronomy'],
        'budget_range': 'medium',
    }


@pytest.fixture
def minimal_profile_data():
    """Minimal valid profile setup (one selection per field)."""
    return {
        'preferred_place_types': ['cafe'],
        'preferred_atmospheres': ['quiet'],
        'preferred_activities': ['live_music'],
        'budget_range': 'low',
    }


# ============================================================================
# TEST MARKERS
# ============================================================================

@pytest.fixture(scope='session')
def django_db_setup():
    """Disable database interactions for tests that don't need them."""
    pass
