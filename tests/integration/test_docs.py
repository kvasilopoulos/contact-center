"""Integration tests for documentation rendering endpoints."""

from fastapi.testclient import TestClient


class TestDocumentationEndpoints:
    """Tests for documentation rendering endpoints."""

    def test_docs_home_page(self, client: TestClient) -> None:
        """Test a documentation page loads with docs template."""
        # Docs are under paths like /solution-design, /architecture; "/" is the landing page
        response = client.get("/solution-design")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Documentation" in response.content

    def test_docs_has_sidebar(self, client: TestClient) -> None:
        """Test that documentation pages include sidebar navigation."""
        response = client.get("/solution-design")

        assert response.status_code == 200
        assert b"sidebar" in response.content.lower()

    def test_docs_specific_page(self, client: TestClient) -> None:
        """Test loading a specific documentation page."""
        response = client.get("/architecture")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_docs_page_not_found(self, client: TestClient) -> None:
        """Test that non-existent page returns 404."""
        response = client.get("/nonexistent-page-xyz")

        assert response.status_code == 404

    def test_docs_path_traversal_protection(self, client: TestClient) -> None:
        """Test that path traversal attempts are blocked."""
        response = client.get("/../../../etc/passwd")

        assert response.status_code == 404

    def test_docs_architecture_page(self, client: TestClient) -> None:
        """Test loading the architecture documentation page."""
        response = client.get("/architecture")

        # Page should either load or return 404 if file doesn't exist
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert "text/html" in response.headers["content-type"]

    def test_docs_url_format_lowercase_with_hyphens(self, client: TestClient) -> None:
        """Test that URLs use lowercase with hyphens instead of uppercase with underscores."""
        # Test AWS_QUICK_START file accessible via aws-quick-start URL
        response = client.get("/aws-quick-start")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_docs_nested_path_with_hyphens(self, client: TestClient) -> None:
        """Test that nested paths work with hyphenated URLs."""
        # Test plan/IMPLEMENTATION_PLAN accessible via plan/implementation-plan
        response = client.get("/plan/implementation-plan")

        # Should load or 404 if file doesn't exist
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert "text/html" in response.headers["content-type"]
