from unittest.mock import patch

import httpx
import pytest
import requests
from fastapi.testclient import TestClient
from groq import APIError as GroqAPIError

from main import app
from services.rate_limit import clear_rate_limits

MOCK_MILK = {
    "name": "Milk 2L",
    "brand": "woolworths",
    "price": 2.50,
    "size": "2L",
    "on_special": False,
}


@pytest.fixture(autouse=True)
def reset_limits():
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.fixture
def client():
    return TestClient(app)


def _groq_api_error() -> GroqAPIError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return GroqAPIError("service unavailable", request, body=None)


def _http_error(status_code: int = 500) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    return requests.HTTPError("upstream error", response=response)


@patch("services.compare.search_coles")
@patch("services.compare.search_woolworths")
def test_compare_store_timeout_returns_504(mock_woolworths, mock_coles, client):
    mock_woolworths.side_effect = requests.Timeout("timed out")
    mock_coles.return_value = [MOCK_MILK]

    response = client.post("/api/compare", json={"items": ["milk"]})

    assert response.status_code == 504
    assert response.json() == {
        "detail": "Store price lookup timed out. Try again.",
    }


@patch("services.compare.search_coles")
@patch("services.compare.search_woolworths")
def test_compare_store_connection_error_returns_503(mock_woolworths, mock_coles, client):
    mock_woolworths.side_effect = requests.ConnectionError("connection refused")
    mock_coles.return_value = [MOCK_MILK]

    response = client.post("/api/compare", json={"items": ["milk"]})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Unable to reach store price service. Try again.",
    }


@patch("services.compare.search_coles")
@patch("services.compare.search_woolworths")
def test_compare_store_http_error_returns_502(mock_woolworths, mock_coles, client):
    mock_woolworths.side_effect = _http_error(500)
    mock_coles.return_value = [MOCK_MILK]

    response = client.post("/api/compare", json={"items": ["milk"]})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Store price lookup failed. Try again.",
    }


@patch("services.compare.search_coles")
@patch("services.compare.search_woolworths")
def test_compare_store_request_exception_returns_502(mock_woolworths, mock_coles, client):
    mock_woolworths.side_effect = requests.RequestException("request failed")
    mock_coles.return_value = [MOCK_MILK]

    response = client.post("/api/compare", json={"items": ["milk"]})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Store price lookup failed. Try again.",
    }


@patch("services.compare.search_coles")
@patch("services.compare.search_woolworths")
def test_compare_invalid_store_json_returns_502(mock_woolworths, mock_coles, client):
    mock_woolworths.side_effect = ValueError("invalid json")
    mock_coles.return_value = [MOCK_MILK]

    response = client.post("/api/compare", json={"items": ["milk"]})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Store returned invalid data. Try again.",
    }


@patch("services.compare.rerank_with_groq")
@patch("services.compare.search_coles")
@patch("services.compare.search_woolworths")
def test_compare_groq_error_returns_502(
    mock_woolworths, mock_coles, mock_rerank, client
):
    mock_woolworths.return_value = [MOCK_MILK]
    mock_coles.return_value = [{**MOCK_MILK, "brand": "coles"}]
    mock_rerank.side_effect = _groq_api_error()

    response = client.post(
        "/api/compare",
        json={"items": ["milk"], "source": "receipt"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Product matching unavailable. Try again.",
    }


@patch("services.compare.search_coles")
@patch("services.compare.search_woolworths")
def test_compare_unexpected_error_returns_500(mock_woolworths, mock_coles, client):
    mock_woolworths.side_effect = RuntimeError("unexpected")
    mock_coles.return_value = [MOCK_MILK]

    response = client.post("/api/compare", json={"items": ["milk"]})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Comparison failed. Try again later.",
    }
