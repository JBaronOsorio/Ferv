"""
Tests for Pipeline C — exploratory recommendation.
"""

import json
import math
import random
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from graph.models import GraphNode
from places.models import Place
from recommendation import recommendation_service
from recommendation import vector_utils
from recommendation.models import LlmInteractionLog
from recommendation.recommendation_service import RecommendationService


# ── vector_utils unit tests ──────────────────────────────────────────────────

class TestVectorUtils:
    def test_random_unit_vector_is_normalized(self):
        rng = random.Random(42)
        v = vector_utils.random_unit_vector(8, rng=rng)
        assert len(v) == 8
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, abs_tol=1e-9)

    def test_random_unit_vector_is_deterministic_with_seed(self):
        v1 = vector_utils.random_unit_vector(16, rng=random.Random(7))
        v2 = vector_utils.random_unit_vector(16, rng=random.Random(7))
        assert v1 == v2

    def test_random_unit_vector_rejects_nonpositive_dim(self):
        with pytest.raises(ValueError):
            vector_utils.random_unit_vector(0)

    def test_vector_add_scaled(self):
        result = vector_utils.vector_add_scaled([1.0, 2.0, 3.0], [10.0, 20.0, 30.0], 0.5)
        assert result == [6.0, 12.0, 18.0]

    def test_vector_add_scaled_length_mismatch(self):
        with pytest.raises(ValueError):
            vector_utils.vector_add_scaled([1.0, 2.0], [1.0, 2.0, 3.0], 1.0)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_mock_candidate(place):
    return {"place": place, "distance": 0.5}


def _patch_pipeline_c(monkeypatch, *, broad_places, direction_places, llm_picks):
    """
    Wire up patches for EmbeddingService, Retriever, LlmClient inside
    recommendation_service so recommend_exploratory runs without external calls.

    Returns (mock_embedder, mock_retriever, mock_llm) for assertions.
    """
    # Shrink constants so a small fixture set is enough.
    monkeypatch.setattr(recommendation_service, "EXPLORATORY_K", len(broad_places))
    monkeypatch.setattr(
        recommendation_service, "EXPLORATORY_K_TOP",
        len(broad_places) - max(len(llm_picks), 1),
    )
    monkeypatch.setattr(recommendation_service, "EXPLORATORY_D", len(direction_places))
    monkeypatch.setattr(recommendation_service, "EXPLORATORY_N", len(llm_picks))

    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3, 0.4]
    mock_embedder.model_name = "mock-embed-model"

    mock_retriever = MagicMock()

    def get_candidates(query_vector, top_k, exclude_user=None):
        # First call (direction probes) has exclude_user=None.
        # Subsequent call (broad retrieval) has exclude_user set.
        if exclude_user is None:
            return [_make_mock_candidate(p) for p in direction_places][:top_k]
        return [_make_mock_candidate(p) for p in broad_places][:top_k]

    mock_retriever.get_candidates.side_effect = get_candidates

    mock_llm = MagicMock()
    mock_llm.model_name = "mock-llm-model"
    mock_llm.send.return_value = (
        {"recommendations": llm_picks},
        json.dumps({"recommendations": llm_picks}),
    )

    monkeypatch.setattr(
        recommendation_service, "EmbeddingService", lambda *a, **kw: mock_embedder
    )
    monkeypatch.setattr(
        recommendation_service, "Retriever", lambda *a, **kw: mock_retriever
    )
    monkeypatch.setattr(
        recommendation_service, "LlmClient", lambda *a, **kw: mock_llm
    )

    return mock_embedder, mock_retriever, mock_llm


def _make_place(idx: int) -> Place:
    return Place.objects.create(
        place_id=f"exp_place_{idx:03d}",
        name=f"Place {idx}",
        address=f"Calle {idx}",
        neighborhood="Test",
        latitude=6.25 + idx * 0.001,
        longitude=-75.56,
        rating=4.0,
        price_level=2,
        review_count=10,
        editorial_summary=f"Summary {idx}",
    )


# ── Service tests ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRecommendExploratory:

    def test_happy_path_creates_nodes_and_logs(
        self, monkeypatch, test_user_with_profile
    ):
        # 5 broad places; K_TOP will become 3 → margin is the last 2.
        broad = [_make_place(i) for i in range(5)]
        direction = [_make_place(i) for i in range(100, 102)]
        margin_picks = [
            {"place_id": broad[3].place_id, "rationale": "stretch one"},
            {"place_id": broad[4].place_id, "rationale": "stretch two"},
        ]
        _patch_pipeline_c(
            monkeypatch,
            broad_places=broad,
            direction_places=direction,
            llm_picks=margin_picks,
        )

        nodes = RecommendationService().recommend_exploratory(
            test_user_with_profile, heat=0.5
        )

        assert len(nodes) == 2
        assert {n.place.place_id for n in nodes} == {broad[3].place_id, broad[4].place_id}
        assert all(n.status == "recommendation" for n in nodes)
        assert GraphNode.objects.filter(user=test_user_with_profile).count() == 2

        log = LlmInteractionLog.objects.latest()
        assert log.workflow == "exploratory_recommendation"
        assert log.outcome == "success"
        assert log.input_payload["heat"] == 0.5
        assert log.input_payload["direction_decoded_place_ids"] == [
            p.place_id for p in direction
        ]
        assert log.input_payload["margin_candidate_place_ids"] == [
            broad[3].place_id, broad[4].place_id,
        ]
        assert "profile_embedding_hash" in log.input_payload

    def test_rejects_picks_outside_margin(
        self, monkeypatch, test_user_with_profile
    ):
        broad = [_make_place(i) for i in range(5)]
        direction = [_make_place(i) for i in range(100, 102)]
        # broad[0] is in the top exclusion zone, not the margin → must be rejected.
        bad_picks = [
            {"place_id": broad[0].place_id, "rationale": "should fail"},
            {"place_id": broad[4].place_id, "rationale": "ok"},
        ]
        _patch_pipeline_c(
            monkeypatch,
            broad_places=broad,
            direction_places=direction,
            llm_picks=bad_picks,
        )

        with pytest.raises(ValueError, match="outside the margin block"):
            RecommendationService().recommend_exploratory(
                test_user_with_profile, heat=0.7
            )

        # No nodes written.
        assert GraphNode.objects.filter(user=test_user_with_profile).count() == 0
        # Log row written with validation_error.
        log = LlmInteractionLog.objects.latest()
        assert log.workflow == "exploratory_recommendation"
        assert log.outcome == "validation_error"

    def test_invalid_heat_raises_before_any_work(self, test_user_with_profile):
        svc = RecommendationService()
        logs_before = LlmInteractionLog.objects.count()
        for bad in (-0.1, 1.5, "0.5", None):
            with pytest.raises(ValueError, match="heat"):
                svc.recommend_exploratory(test_user_with_profile, heat=bad) #type: ignore
        # Nothing written.
        assert LlmInteractionLog.objects.count() == logs_before

    def test_empty_margin_raises(self, monkeypatch, test_user_with_profile):
        # Broad set is exactly K_TOP → margin is empty.
        broad = [_make_place(i) for i in range(3)]
        direction = [_make_place(i) for i in range(100, 102)]
        _patch_pipeline_c(
            monkeypatch,
            broad_places=broad,
            direction_places=direction,
            llm_picks=[{"place_id": broad[0].place_id, "rationale": "x"}],
        )
        # _patch_pipeline_c sets K_TOP = len(broad) - len(llm_picks) = 2.
        # Force K_TOP to swallow the whole broad set instead.
        monkeypatch.setattr(recommendation_service, "EXPLORATORY_K_TOP", 3)

        with pytest.raises(ValueError, match="not enough candidates"):
            RecommendationService().recommend_exploratory(
                test_user_with_profile, heat=0.0
            )


# ── View tests ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExploratoryEndpoint:

    def test_requires_authentication(self, client):
        from django.conf import settings
        
        url = reverse("recommendation:exploratory")
        response = client.post(
            url, data=json.dumps({"heat": 0.5}), content_type="application/json"
        )
        assert response.status_code == 302  # redirect to login
        assert response.url.startswith(settings.LOGIN_URL)

    def test_invalid_json(self, authenticated_client):
        url = reverse("recommendation:exploratory")
        response = authenticated_client.post(
            url, data="not json", content_type="application/json"
        )
        assert response.status_code == 400

    @pytest.mark.parametrize("payload", [{}, {"heat": "0.5"}, {"heat": 1.5}, {"heat": -0.1}])
    def test_rejects_bad_heat(self, authenticated_client, payload):
        url = reverse("recommendation:exploratory")
        response = authenticated_client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 400

    def test_happy_path_endpoint(
        self, monkeypatch, authenticated_client, test_user_with_profile
    ):
        broad = [_make_place(i) for i in range(5)]
        direction = [_make_place(i) for i in range(100, 102)]
        picks = [{"place_id": broad[4].place_id, "rationale": "stretch"}]
        _patch_pipeline_c(
            monkeypatch,
            broad_places=broad,
            direction_places=direction,
            llm_picks=picks,
        )

        url = reverse("recommendation:exploratory")
        response = authenticated_client.post(
            url, data=json.dumps({"heat": 0.4}), content_type="application/json"
        )
        assert response.status_code == 200
        body = json.loads(response.content)
        assert len(body["nodes"]) == 1
        assert body["nodes"][0]["place"]["place_id"] == broad[4].place_id
