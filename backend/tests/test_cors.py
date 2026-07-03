from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_compare_preflight_allows_frugl_production_origin():
    response = client.options(
        "/api/compare",
        headers={
            "Origin": "https://frugl.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frugl.vercel.app"


def test_compare_preflight_allows_frugl_preview_origin():
    response = client.options(
        "/api/compare",
        headers={
            "Origin": "https://frugl-git-main-chrisvaldar.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://frugl-git-main-chrisvaldar.vercel.app"
    )
