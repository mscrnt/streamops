import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    
    @pytest.mark.unit
    def test_liveness_check(self, client):
        """Test liveness check endpoint."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}
    
    @pytest.mark.unit
    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "checks" in data
        assert "timestamp" in data


class TestAssetEndpoints:
    
    @pytest.mark.api
    def test_list_assets(self, client):
        """Test listing assets."""
        response = client.get("/api/assets")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
    
    @pytest.mark.api
    def test_create_asset(self, client, sample_asset_data):
        """Test creating an asset."""
        response = client.post("/api/assets", json=sample_asset_data)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_asset_data["id"]
    
    @pytest.mark.api
    def test_get_asset(self, client):
        """Test getting a specific asset."""
        response = client.get("/api/assets/asset_123")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "asset_123"
    
    @pytest.mark.api
    def test_asset_search(self, client):
        """Test asset search."""
        response = client.post("/api/assets/search", json={
            "query": "test",
            "filters": {"container": "mp4"}
        })
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestJobEndpoints:
    
    @pytest.mark.api
    def test_list_jobs(self, client):
        """Test listing jobs."""
        response = client.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    
    @pytest.mark.api
    def test_create_job(self, client, sample_job_data):
        """Test creating a job."""
        response = client.post("/api/jobs", json=sample_job_data)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_job_data["id"]
        assert data["status"] == "queued"
    
    @pytest.mark.api
    def test_get_job(self, client):
        """Test getting a specific job."""
        response = client.get("/api/jobs/job_123")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "job_123"
    
    @pytest.mark.api
    def test_cancel_job(self, client):
        """Test canceling a job."""
        response = client.post("/api/jobs/job_123/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Job cancelled successfully"


class TestRuleEndpoints:
    
    @pytest.mark.api
    def test_list_rules(self, client):
        """Test listing rules."""
        response = client.get("/api/rules")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    
    @pytest.mark.api
    def test_create_rule(self, client, sample_rule_data):
        """Test creating a rule."""
        response = client.post("/api/rules", json=sample_rule_data)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_rule_data["id"]
        assert data["name"] == sample_rule_data["name"]
    
    @pytest.mark.api
    def test_test_rule(self, client):
        """Test testing a rule."""
        response = client.post("/api/rules/rule_123/test", json={
            "test_data": {"path": "/test/file.mkv"}
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data


class TestConfigEndpoints:
    
    @pytest.mark.api
    def test_list_config(self, client):
        """Test listing configuration."""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    
    @pytest.mark.api
    def test_update_config(self, client):
        """Test updating configuration."""
        response = client.put("/api/config/test_key", json={
            "value": "test_value"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "test_key"
        assert data["value"] == "test_value"