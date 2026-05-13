"""
conftest.py
-----------
Pytest configuration for the graph app.
App-specific fixtures can be added here.
"""

import pytest
from graph.models import GraphNode, GraphEdge
from places.models import Place


@pytest.fixture
def graph_test_data(test_user_with_profile, test_place, test_place_2):
    """Create a complete graph with multiple nodes and edges."""
    node1 = GraphNode.objects.create(
        user=test_user_with_profile,
        place=test_place,
        status='in_graph',
        is_favorite=True,
    )
    node2 = GraphNode.objects.create(
        user=test_user_with_profile,
        place=test_place_2,
        status='in_graph',
    )
    edge = GraphEdge.objects.create(
        user=test_user_with_profile,
        from_node=node1,
        to_node=node2,
        weight=0.9,
    )
    return {'nodes': [node1, node2], 'edge': edge}
