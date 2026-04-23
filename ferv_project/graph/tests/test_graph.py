"""
Tests for graph node management.

HU01: Add Node (Promote Recommendation to Graph)
- Happy path: successfully add node to graph
- Alternative: reject duplicate node (unique constraint)

HU09: Delete Node
- Happy path: successfully delete node
- Alternative: error when deleting non-existent node
- Note: HU09 tests marked with @skip until endpoint is implemented
"""

import json
from urllib import response
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from graph.models import GraphNode, GraphEdge
from places.models import Place

User = get_user_model()


@pytest.mark.django_db
class TestAddNode:
    """Tests for add_node endpoint (POST /graph/add-node/)."""

    def test_add_node_successful(self, client, test_user_with_profile, test_place):
        """
        HU01 — Happy Path: User successfully adds a node to their graph.
        
        Given: Authenticated user, place exists
        When: POST /graph/add-node/ with valid node_id
        Then: GraphNode created with status='in_graph', returns edge_ids
        """
        client.force_login(test_user_with_profile)
        
        # Create a recommendation node first
        node = GraphNode.objects.create(
            user=test_user_with_profile,
            place=test_place,
            rationale='Test recommendation',
            status='recommendation',
        )
        
        url = reverse('graph:add-node')
        data = json.dumps({'node_id': node.id})
        
        response = client.post(
            url,
            data=data,
            content_type='application/json',
        )
        
        assert response.status_code == 200
        response_data = json.loads(response.content)
        assert 'edge_ids' in response_data

    def test_add_node_duplicate_rejected(self, client, test_user_with_profile, test_place):
        """
        HU01 — Alternative: Reject duplicate node (unique constraint).
        
        Given: User already has a node for this place
        When: POST /graph/add-node/ with same node_id
        Then: Return 400 error (duplicate would violate constraint)
        """
        client.force_login(test_user_with_profile)
        
        # Hacer dos posts con el mismo node_id
        node = GraphNode.objects.create(
            user=test_user_with_profile,
            place=test_place,
            rationale='Test recommendation',
            status='recommendation',
        )
        url = reverse('graph:add-node')
        data = json.dumps({'node_id': node.id})
        # Primer post - should succeed
        response1 = client.post(
            url,
            data=data,
            content_type='application/json',
        )
        assert response1.status_code == 200
        # Segundo post - should fail due to duplicate
        response2 = client.post(
            url,
            data=data,
            content_type='application/json',
        )
        
        # Should error due to duplicate
        assert response2.status_code == 400

    def test_add_node_requires_authentication(self, client, test_place):
        """
        HU07 — Alternative: Unauthenticated user cannot add nodes.
        
        Given: Anonymous user
        When: POST /graph/add-node/
        Then: Redirect to login
        """
        url = reverse('graph:add-node')
        response = client.post(url, {})
        
        assert response.status_code == 302


    def test_add_node_invalid_json(self, client, test_user_with_profile):
        """
        HU01 — Alternative: Invalid JSON returns 400.
        
        Given: POST request with malformed JSON
        When: POST /graph/add-node/
        Then: Return 400 with error message
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:add-node')
        
        response = client.post(
            url,
            data='invalid json',
            content_type='application/json',
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.content)
        assert 'error' in response_data

    def test_add_node_missing_node_id(self, client, test_user_with_profile):
        """
        HU01 — Alternative: Missing node_id returns 400.
        
        Given: POST request without node_id field
        When: POST /graph/add-node/
        Then: Return 400 with error message
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:add-node')
        data = json.dumps({})
        
        response = client.post(
            url,
            data=data,
            content_type='application/json',
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.content)
        assert 'error' in response_data


@pytest.mark.django_db
class TestGraphFetch:
    """Tests for fetch_graph API endpoint (GET /graph/api/fetch-graph/)."""

    def test_fetch_graph_user_nodes(self, client, test_user_with_profile, test_graph_node):
        """
        HU01 — Happy Path: Fetch user's graph nodes and edges.
        
        Given: Authenticated user with graph nodes
        When: GET /graph/api/fetch_graph/
        Then: Return JSON with user's nodes and edges
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:fetch-graph')
        
        response = client.get(url)
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'nodes' in data
        assert 'edges' in data
        assert len(data['nodes']) > 0

    def test_fetch_graph_empty_user(self, client, test_user_with_profile):
        """
        HU01 — Alternative: User with no nodes gets empty graph.
        
        Given: Authenticated user with no nodes
        When: GET /graph/api/fetch_graph/
        Then: Return empty nodes and edges arrays
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:fetch-graph')
        
        response = client.get(url)
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['nodes'] == []
        assert data['edges'] == []

    def test_fetch_graph_requires_authentication(self, client):
        """
        HU07 — Alternative: Unauthenticated user cannot fetch graph.
        
        Given: Anonymous user
        When: GET /graph/api/fetch_graph/
        Then: Redirect to login
        """
        url = reverse('graph:fetch-graph')
        response = client.get(url)
        
        assert response.status_code == 302


@pytest.mark.skip(reason="Endpoint pendiente de implementar — HU09")
@pytest.mark.django_db
class TestDeleteNode:
    """Tests for delete_node endpoint (DELETE /graph/delete-node/<node_id>)."""

    def test_delete_node_successful(self, client, test_user_with_profile, test_graph_node):
        """
        HU09 — Happy Path: User successfully deletes a node from their graph.
        
        Given: Authenticated user with existing graph node
        When: DELETE /graph/delete-node/<node_id>
        Then: Node and associated edges are deleted, return confirmation
        """
        client.force_login(test_user_with_profile)
        node_id = test_graph_node.id
        url = reverse('graph:delete-node', kwargs={'node_id': node_id})
        
        response = client.delete(url)
        
        assert response.status_code == 200
        response_data = json.loads(response.content)
        assert response_data.get('success') is True
        
        # Verify node is deleted
        assert not GraphNode.objects.filter(id=node_id).exists()
        # Verify edges are also deleted
        assert not GraphEdge.objects.filter(
            from_node_id=node_id
        ) | GraphEdge.objects.filter(to_node_id=node_id)

    def test_delete_node_nonexistent(self, client, test_user_with_profile):
        """
        HU09 — Alternative: Deleting non-existent node returns 404.
        
        Given: Authenticated user, node doesn't exist
        When: DELETE /graph/delete-node/9999
        Then: Return 404 error
        """
        client.force_login(test_user_with_profile)
        url = reverse('graph:delete-node', kwargs={'node_id': 9999})
        
        response = client.delete(url)
        
        assert response.status_code == 404

    def test_delete_node_requires_authentication(self, client):
        """
        HU07 — Alternative: Unauthenticated user cannot delete nodes.
        
        Given: Anonymous user
        When: DELETE /graph/delete-node/<node_id>
        Then: Redirect to login
        """
        url = reverse('graph:delete-node', kwargs={'node_id': 1})
        response = client.delete(url)
        
        assert response.status_code == 302


    def test_delete_node_permission_check(self, client, test_user, test_graph_node):
        """
        HU09 — Alternative: User cannot delete another user's node.
        
        Given: Authenticated user who doesn't own the node
        When: DELETE /graph/delete-node/<node_id_of_other_user>
        Then: Return 403 Forbidden
        """
        client.force_login(test_user)
        url = reverse('graph:delete-node', kwargs={'node_id': test_graph_node.id})
        
        response = client.delete(url)
        
        assert response.status_code == 403
