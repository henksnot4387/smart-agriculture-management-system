from app.middleware.request_logging import _normalize_error_code, _resolve_domain


def test_normalize_error_code_with_symbols() -> None:
    assert _normalize_error_code("value_error.missing field") == "VALUE_ERROR_MISSING_FIELD"


def test_normalize_error_code_empty() -> None:
    assert _normalize_error_code("") is None
    assert _normalize_error_code(None) is None


def test_resolve_domain_sensor() -> None:
    assert _resolve_domain("/api/sensor/raw") == "sensor"
    assert _resolve_domain("/integrations/hoogendoorn/sync") == "sensor"


def test_resolve_domain_vision() -> None:
    assert _resolve_domain("/api/vision/tasks") == "vision"
    assert _resolve_domain("/api/ws/vision/tasks") == "vision"


def test_resolve_domain_copilot_scheduler_tasks() -> None:
    assert _resolve_domain("/api/ai-insights/summary") == "ai-insights"
    assert _resolve_domain("/api/copilot/summary") == "ai-insights"
    assert _resolve_domain("/api/admin/scheduler/jobs") == "scheduler"
    assert _resolve_domain("/api/tasks/123") == "tasks"


def test_resolve_domain_observability() -> None:
    assert _resolve_domain("/api/admin/observability/overview") == "observability"
