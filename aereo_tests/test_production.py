"""Release smoke coverage without requiring a Docker daemon in GitHub CI."""
from fastapi.testclient import TestClient
from aereo.production import create_production_app


def test_same_origin_spa_and_api(tmp_path):
    web = tmp_path / "dist"
    (web / "assets").mkdir(parents=True)
    (web / "samples").mkdir()
    (web / "index.html").write_text("<html>GeoInsight test shell</html>", encoding="utf-8")
    (web / "assets" / "bundle.js").write_text("console.log('ok')", encoding="utf-8")
    (web / "samples" / "sample.kml").write_text("<kml/>", encoding="utf-8")
    app = create_production_app(frontend_dir=web, database_url=f'sqlite:///{tmp_path / "prod.db"}')
    with TestClient(app) as client:
        assert client.get("/", follow_redirects=False).headers["location"] == "/geospatial"
        assert client.get("/geospatial").status_code == 200
        assert client.get("/geospatial/quality").status_code == 200
        assert client.get("/geospatial/compare").status_code == 200
        assert client.get("/geospatial/topology").status_code == 200
        assert client.get("/geospatial/routes").status_code == 200
        assert client.get("/geospatial/guide").status_code == 200
        assert "GeoInsight test shell" in client.get("/geospatial").text
        assert client.get("/assets/bundle.js").status_code == 200
        assert client.get("/samples/sample.kml").status_code == 200
        assert client.get("/health").json() == {"status": "healthy"}
        assert client.get("/docs").status_code == 200
        assert client.get("/api/files/not-real/").status_code == 404
        assert client.get("/api/missing/").status_code == 404
        assert client.get("/nonexistent-page").status_code == 404
