"""
Tests for Pipeline B — node-based recommendation.

Mirrors test_exploratory.py: real DB writes for GraphNode / LlmInteractionLog,
but EmbeddingService / Retriever / LlmClient and the embedding-vector lookup
are patched so no external calls are made.
"""

import json
from unittest.mock import MagicMock

import pytest
from django.urls import reverse

from graph.models import GraphNode
from places.models import Place
from recommendation import recommendation_service, vector_utils
from recommendation.models import LlmInteractionLog
from recommendation.recommendation_service import RecommendationService


# ── reciprocal_rank_fusion unit tests ────────────────────────────────────────

class TestReciprocalRankFusion:
    def test_empty_input(self):
        assert vector_utils.reciprocal_rank_fusion([]) == []

    def test_single_list_passthrough(self):
        result = vector_utils.reciprocal_rank_fusion([["a", "b", "c"]], c=60)
        assert [k for k, _ in result] == ["a", "b", "c"]
        # Scores strictly decreasing.
        scores = [s for _, s in result]
        assert scores[0] > scores[1] > scores[2]

    def test_overlap_boosts_rank(self):
        # 'b' appears at rank 0 in list 2 and rank 1 in list 1; 'a' only at rank 0 in list 1.
        result = vector_utils.reciprocal_rank_fusion(
            [["a", "b"], ["b", "c"]], c=60
        )
        ranking = [k for k, _ in result]
        assert ranking[0] == "b"  # appearing in both lists wins
        assert set(ranking) == {"a", "b", "c"}

    def test_known_scores(self):
        # c=0 makes the math easy: 1/(rank+1).
        result = vector_utils.reciprocal_rank_fusion(
            [["a", "b"], ["b", "a"]], c=0
        )
        score_map = dict(result)
        # a: 1/1 (list1 rank 0) + 1/2 (list2 rank 1) = 1.5
        # b: 1/2 (list1 rank 1) + 1/1 (list2 rank 0) = 1.5
        assert score_map["a"] == pytest.approx(1.5)
        assert score_map["b"] == pytest.approx(1.5)

    def test_duplicates_within_list_count_once(self):
        result_dup = vector_utils.reciprocal_rank_fusion([["a", "a", "b"]], c=60)
        result_no_dup = vector_utils.reciprocal_rank_fusion([["a", "b"]], c=60)
        # Same item count and same first-rank score for 'a'.
        assert dict(result_dup)["a"] == pytest.approx(dict(result_no_dup)["a"])

    def test_deterministic_tiebreak_by_first_seen(self):
        # Two completely disjoint lists, identical lengths → first-seen breaks ties.
        result = vector_utils.reciprocal_rank_fusion(
            [["a"], ["b"]], c=60
        )
        # 'a' was seen first.
        assert [k for k, _ in result] == ["a", "b"]

    def test_negative_c_rejected(self):
        with pytest.raises(ValueError):
            vector_utils.reciprocal_rank_fusion([["a"]], c=-1)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_place(idx: int) -> Place:
    return Place.objects.create(
        place_id=f"nb_place_{idx:03d}",
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


def _patch_pipeline_b(
    monkeypatch,
    *,
    per_anchor_results: list[list[Place]],
    llm_picks: list[dict],
    n_override: int | None = None,
):
    """
    Wire patches for EmbeddingService / Retriever / LlmClient / _anchor_vectors
    so recommend_node_based runs without external calls or PlaceEmbedding rows.

    `per_anchor_results[i]` is the candidate Place list returned for anchor i.
    """
    n = n_override if n_override is not None else len(llm_picks)
    monkeypatch.setattr(recommendation_service, "NODE_BASED_N", n)
    # Keep RRF fusion realistic but cap so all candidates flow through.
    fused_candidate_count = sum(len(r) for r in per_anchor_results)
    monkeypatch.setattr(
        recommendation_service, "NODE_BASED_K",
        max(fused_candidate_count, 1),
    )

    mock_embedder = MagicMock()
    mock_embedder.model_name = "mock-embed-model"
    mock_embedder.vector_class = MagicMock()  # only identity matters

    mock_retriever = MagicMock()
    call_log: list[dict] = []
    iter_results = iter(per_anchor_results)

    def get_candidates(query_vector, top_k, exclude_user=None):
        try:
            places = next(iter_results)
        except StopIteration:
            places = []
        call_log.append(
            {"top_k": top_k, "exclude_user": exclude_user, "n_places": len(places)}
        )
        return [{"place": p, "distance": 0.5} for p in places][:top_k]

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

    # Bypass the real PlaceEmbedding lookup — return a dummy vector per anchor place.
    def fake_anchor_vectors(places, vector_class):
        return {p.pk: [0.1, 0.2, 0.3] for p in places}

    monkeypatch.setattr(
        recommendation_service, "_anchor_vectors", fake_anchor_vectors
    )

    return mock_embedder, mock_retriever, mock_llm, call_log


def _make_anchor(user, place, status="in_graph"):
    return GraphNode.objects.create(
        user=user, place=place, status=status, rationale="seed"
    )


# ── Service tests ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRecommendNodeBased:

    def test_happy_path_creates_nodes_and_logs(
        self, monkeypatch, test_user_with_profile
    ):
        anchor_places = [_make_place(i) for i in range(3)]
        anchors = [_make_anchor(test_user_with_profile, p) for p in anchor_places]
        # 3 anchors → 3 disjoint candidate lists of 2 places each.
        cand_places = [_make_place(100 + i) for i in range(6)]
        per_anchor = [
            [cand_places[0], cand_places[1]],
            [cand_places[2], cand_places[3]],
            [cand_places[4], cand_places[5]],
        ]
        picks = [
            {"place_id": cand_places[0].place_id, "rationale": "extends quiet vibe"},
            {"place_id": cand_places[2].place_id, "rationale": "matches taste"},
        ]
        _, _, _, call_log = _patch_pipeline_b(
            monkeypatch,
            per_anchor_results=per_anchor,
            llm_picks=picks,
        )

        nodes = RecommendationService().recommend_node_based(
            test_user_with_profile, [a.id for a in anchors]
        )

        assert len(nodes) == 2
        assert {n.place.place_id for n in nodes} == {
            cand_places[0].place_id, cand_places[2].place_id,
        }
        assert all(n.status == "recommendation" for n in nodes)

        # 3 anchors → 3 retriever calls, all with exclude_user set.
        assert len(call_log) == 3
        assert all(c["exclude_user"] == test_user_with_profile for c in call_log)
        assert all(c["top_k"] == recommendation_service.NODE_BASED_K_PRIME for c in call_log)

        log = LlmInteractionLog.objects.latest()
        assert log.workflow == "node_based_recommendation"
        assert log.outcome == "success"
        assert log.input_payload["anchor_node_ids"] == [a.id for a in anchors]
        assert log.input_payload["anchor_place_ids"] == [p.place_id for p in anchor_places]
        assert len(log.input_payload["per_anchor_retrieval"]) == 3
        assert len(log.input_payload["fused_top_k"]) == 6  # all candidates fused

    def test_rejects_picks_outside_fused_set(
        self, monkeypatch, test_user_with_profile
    ):
        anchor_place = _make_place(0)
        anchor = _make_anchor(test_user_with_profile, anchor_place)
        cand_places = [_make_place(100 + i) for i in range(3)]
        # Pick a place_id that was never in the fused candidate set.
        rogue = _make_place(999)
        picks = [{"place_id": rogue.place_id, "rationale": "should fail"}]
        _patch_pipeline_b(
            monkeypatch,
            per_anchor_results=[cand_places],
            llm_picks=picks,
        )

        with pytest.raises(ValueError, match="outside the fused candidate set"):
            RecommendationService().recommend_node_based(
                test_user_with_profile, [anchor.id]
            )

        # No new recommendation node was written.
        assert GraphNode.objects.filter(
            user=test_user_with_profile, status="recommendation"
        ).count() == 0
        log = LlmInteractionLog.objects.latest()
        assert log.workflow == "node_based_recommendation"
        assert log.outcome == "validation_error"

    def test_empty_node_ids_raises_immediately(self, test_user_with_profile):
        svc = RecommendationService()
        logs_before = LlmInteractionLog.objects.count()
        for bad in ([], None, "53", [1, "two"], [1, True]):
            with pytest.raises(ValueError):
                svc.recommend_node_based(test_user_with_profile, bad)  # type: ignore
        assert LlmInteractionLog.objects.count() == logs_before

    def test_anchor_not_owned_by_user_raises(
        self, monkeypatch, test_user_with_profile
    ):
        # Anchor belongs to a different user.
        from django.contrib.auth import get_user_model
        other = get_user_model().objects.create_user(
            username="other", email="other@x.com", password="x"
        )
        place = _make_place(0)
        foreign_anchor = _make_anchor(other, place)

        # Patch so we'd succeed if we got past validation — we shouldn't.
        _patch_pipeline_b(
            monkeypatch,
            per_anchor_results=[[]],
            llm_picks=[],
        )

        logs_before = LlmInteractionLog.objects.count()
        with pytest.raises(ValueError, match="not owned by user"):
            RecommendationService().recommend_node_based(
                test_user_with_profile, [foreign_anchor.id]
            )
        assert LlmInteractionLog.objects.count() == logs_before

    def test_anchor_with_recommendation_status_raises(
        self, monkeypatch, test_user_with_profile
    ):
        place = _make_place(0)
        wrong_status = _make_anchor(
            test_user_with_profile, place, status="recommendation"
        )

        _patch_pipeline_b(
            monkeypatch,
            per_anchor_results=[[]],
            llm_picks=[],
        )

        logs_before = LlmInteractionLog.objects.count()
        with pytest.raises(ValueError, match="not in_graph"):
            RecommendationService().recommend_node_based(
                test_user_with_profile, [wrong_status.id]
            )
        assert LlmInteractionLog.objects.count() == logs_before

    def test_anchor_without_embedding_raises_before_llm(
        self, monkeypatch, test_user_with_profile
    ):
        from recommendation.models import GeminiEmbeddingVectorLarge

        anchor_place = _make_place(0)
        anchor = _make_anchor(test_user_with_profile, anchor_place)

        # Don't patch _anchor_vectors — let the real one run against a real
        # vector class. No PlaceEmbedding exists for this anchor in the test
        # DB, so the service must raise before any LLM call.
        mock_embedder = MagicMock()
        mock_embedder.model_name = "mock-embed-model"
        mock_embedder.vector_class = GeminiEmbeddingVectorLarge
        mock_retriever = MagicMock()
        mock_llm = MagicMock()
        monkeypatch.setattr(
            recommendation_service, "EmbeddingService",
            lambda *a, **kw: mock_embedder,
        )
        monkeypatch.setattr(
            recommendation_service, "Retriever", lambda *a, **kw: mock_retriever
        )
        monkeypatch.setattr(
            recommendation_service, "LlmClient", lambda *a, **kw: mock_llm
        )

        logs_before = LlmInteractionLog.objects.count()
        with pytest.raises(ValueError, match="without an embedding"):
            RecommendationService().recommend_node_based(
                test_user_with_profile, [anchor.id]
            )
        assert LlmInteractionLog.objects.count() == logs_before
        mock_llm.send.assert_not_called()


# ── View tests ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNodeBasedEndpoint:

    def test_requires_authentication(self, client):
        from django.conf import settings
        url = reverse("recommendation:node_based")
        response = client.post(
            url, data=json.dumps({"node_ids": [1]}), content_type="application/json"
        )
        assert response.status_code == 302
        assert response.url.startswith(settings.LOGIN_URL)

    def test_invalid_json(self, authenticated_client):
        url = reverse("recommendation:node_based")
        response = authenticated_client.post(
            url, data="not json", content_type="application/json"
        )
        assert response.status_code == 400

    @pytest.mark.parametrize("payload", [
        {},
        {"node_ids": []},
        {"node_ids": "53"},
        {"node_ids": [1, "two"]},
        {"node_ids": [1, True]},
    ])
    def test_rejects_bad_node_ids(self, authenticated_client, payload):
        url = reverse("recommendation:node_based")
        response = authenticated_client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 400

    def test_happy_path_endpoint(
        self, monkeypatch, authenticated_client, test_user_with_profile
    ):
        anchor_places = [_make_place(i) for i in range(2)]
        anchors = [_make_anchor(test_user_with_profile, p) for p in anchor_places]
        cand_places = [_make_place(100 + i) for i in range(2)]
        picks = [{"place_id": cand_places[0].place_id, "rationale": "fits"}]
        _patch_pipeline_b(
            monkeypatch,
            per_anchor_results=[
                [cand_places[0]],
                [cand_places[1]],
            ],
            llm_picks=picks,
        )

        url = reverse("recommendation:node_based")
        response = authenticated_client.post(
            url,
            data=json.dumps({"node_ids": [a.id for a in anchors]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        body = json.loads(response.content)
        assert len(body["nodes"]) == 1
        assert body["nodes"][0]["place"]["place_id"] == cand_places[0].place_id
