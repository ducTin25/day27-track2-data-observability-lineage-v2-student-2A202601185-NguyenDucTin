from student_api import downstream_assets


def test_transitive_downstream_assets():
    graph = {
        "raw_orders": ["stg_orders"],
        "stg_orders": ["revenue"],
        "revenue": ["dashboard"],
    }
    assert downstream_assets(graph, "raw_orders") == ["stg_orders", "revenue", "dashboard"]
