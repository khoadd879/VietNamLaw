import json
from unittest.mock import patch

from services.multi_query import expand_query


def test_expand_query_returns_original_plus_variants() -> None:
    payload = json.dumps({"queries": ["Ly hôn đơn phương", "Đơn phương ly hôn thế nào"]})
    with patch("services.multi_query._run_pooled", return_value=payload):
        queries = expand_query("Ly hôn", n_variants=2)
    assert queries[0] == "Ly hôn"
    assert len(queries) == 3
    assert "Ly hôn đơn phương" in queries


def test_expand_query_dedupes_and_preserves_original() -> None:
    payload = json.dumps({"queries": ["Ly hôn", "Ly hôn đơn phương", "Ly hôn"]})
    with patch("services.multi_query._run_pooled", return_value=payload):
        queries = expand_query("Ly hôn", n_variants=3)
    assert queries[0] == "Ly hôn"
    assert queries.count("Ly hôn") == 1
    assert "Ly hôn đơn phương" in queries


def test_expand_query_falls_back_to_original_on_invalid_json() -> None:
    with patch("services.multi_query._run_pooled", return_value="not json"):
        queries = expand_query("Ly hôn", n_variants=2)
    assert queries == ["Ly hôn"]


def test_expand_query_falls_back_on_empty_response() -> None:
    with patch("services.multi_query._run_pooled", return_value=""):
        queries = expand_query("Ly hôn", n_variants=2)
    assert queries == ["Ly hôn"]