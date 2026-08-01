"""
tests/test_dashboard.py
========================
Tests for the Phase 7 dashboard Flask application.

Covers API endpoints and basic page rendering.
"""

from __future__ import annotations

import json
import pytest

from src.output.dashboard import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestDashboardPages:
    def test_dashboard_page_renders(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"Zepto AI Review Engine" in response.data

    def test_dashboard_contains_sections(self, client):
        response = client.get("/")
        assert b"Pipeline Overview" in response.data
        assert b"Insights" in response.data
        assert b"Themes" in response.data
        assert b"Segments" in response.data
        assert b"Reviews" in response.data
        assert b"Evaluation" in response.data


class TestDashboardAPI:
    def test_api_insights(self, client):
        response = client.get("/api/insights")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "insights" in data

    def test_api_themes(self, client):
        response = client.get("/api/themes")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "themes" in data
        assert "count" in data

    def test_api_eval(self, client):
        response = client.get("/api/eval")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "phase" in data
        assert "passed" in data

    def test_api_umap_json(self, client):
        response = client.get("/api/umap")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "points" in data or "count" in data

    def test_api_umap_image(self, client):
        response = client.get("/api/umap?format=image")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "exists" in data

    def test_api_segments(self, client):
        response = client.get("/api/segments")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "segments" in data
        assert "count" in data

    def test_api_stats(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "raw_records" in data
        assert "clean_chunks" in data
        assert "sources" in data
        assert "apps" in data
        assert "total_insights" in data
        assert "total_themes" in data
        assert "eval_passed" in data

    def test_api_reviews(self, client):
        response = client.get("/api/reviews")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "reviews" in data
        assert "count" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_api_reviews_with_filters(self, client):
        response = client.get("/api/reviews?source=play_store&rating=5&page=1&page_size=10")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_api_review_filters(self, client):
        response = client.get("/api/review-filters")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "sources" in data
        assert "apps" in data
        assert "ratings" in data

    def test_api_review_distribution(self, client):
        response = client.get("/api/review-distribution")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "by_source" in data
        assert "by_app" in data
        assert "by_rating" in data
