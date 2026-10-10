"""New C4B deep-link must survive refresh in a single-origin Docker release."""
from fastapi.testclient import TestClient
from aereo.production import create_production_app


def test_spatial_intelligence_spa_deep_link(tmp_path):
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html>GeoInsight Intelligence shell</html>", encoding="utf-8")
    app = create_production_app(frontend_dir=static, database_url=f'sqlite:///{tmp_path / "c4b.db"}')
    with TestClient(app) as client:
        response = client.get("/geospatial/intelligence")
        assert response.status_code == 200
        assert "GeoInsight Intelligence shell" in response.text
        assert client.get("/geospatial/unknown-page").status_code == 404
        assert client.get("/api/analysis/unknown").status_code == 404
