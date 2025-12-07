"""
Tests for API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from api.app import app


client = TestClient(app)


def test_healthz():
    """Test health check endpoint"""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_identify_and_answer():
    """Test identify-and-answer endpoint"""
    # TODO: Implement test
    pass


def test_metrics():
    """Test metrics endpoint"""
    # TODO: Implement test
    pass


