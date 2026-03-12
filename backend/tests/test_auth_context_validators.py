from fastapi import HTTPException
import pytest

from app.api.auth_context import _validate_user_role


def test_validate_user_role_accepts_known_roles() -> None:
    assert _validate_user_role("super_admin") == "SUPER_ADMIN"
    assert _validate_user_role("admin") == "ADMIN"
    assert _validate_user_role("expert") == "EXPERT"
    assert _validate_user_role("worker") == "WORKER"


def test_validate_user_role_rejects_empty() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_user_role("")
    assert exc_info.value.status_code == 401


def test_validate_user_role_rejects_unknown() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_user_role("guest")
    assert exc_info.value.status_code == 403
