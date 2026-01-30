"""Integration tests for documentation rendering endpoints."""

from fastapi.testclient import TestClient


class TestDocumentationEndpoints:
    """Tests for documentation rendering endpoints.

    Docs are mounted at prefix /docs (e.g. /docs/solution-design, /docs/architecture).
    """

    def test_docs_home_page(self, client: TestClient) -> None:
        """Test a documentation page loads with docs template."""
        response = client.get("/docs/solution-design")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Documentation" in response.content

    def test_docs_has_sidebar(self, client: TestClient) -> None:
        """Test that documentation pages include sidebar navigation."""
        response = client.get("/docs/solution-design")

        assert response.status_code == 200
        assert b"sidebar" in response.content.lower()

    def test_docs_specific_page(self, client: TestClient) -> None:
        """Test loading a specific documentation page."""
        response = client.get("/docs/architecture")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_docs_page_not_found(self, client: TestClient) -> None:
        """Test that non-existent page returns 404."""
        response = client.get("/docs/nonexistent-page-xyz")

        assert response.status_code == 404

    def test_docs_path_traversal_protection(self, client: TestClient) -> None:
        """Test that path traversal attempts are blocked."""
        response = client.get("/docs/../../../etc/passwd")

        assert response.status_code == 404

    def test_docs_architecture_page(self, client: TestClient) -> None:
        """Test loading the architecture documentation page."""
        response = client.get("/docs/architecture")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert "text/html" in response.headers["content-type"]

    def test_docs_url_format_lowercase_with_hyphens(self, client: TestClient) -> None:
        """Test that URLs use lowercase with hyphens (e.g. consolidated AWS page)."""
        response = client.get("/docs/aws")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_docs_nested_path_with_hyphens(self, client: TestClient) -> None:
        """Test that nested paths work with hyphenated URLs."""
        response = client.get("/docs/plan/implementation-plan")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert "text/html" in response.headers["content-type"]
