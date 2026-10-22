"""Imports the real app with the real installed packages, which the fake-database flow checks
do not do. Catches a missing dependency, a typo in an import, or a bad setting at startup."""
import importlib
import os

os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("SECRET_KEY", "ci-only-secret-key-0123456789abcdef0123456789")


def test_app_imports_and_registers_routes():
    main = importlib.import_module("app.main")
    paths = set(main.app.openapi()["paths"])
    for expected in (
        "/api/auth/login",
        "/api/projects",
        "/api/payments/verify",
        "/api/payments/webhook",
        "/api/invoices/{token}",
        "/api/support",
        "/api/projects/{project_id}/deliver",
    ):
        assert expected in paths, f"{expected} is not registered"


def test_cors_is_not_wide_open():
    config = importlib.import_module("app.config")
    assert "*" not in config.settings.cors_origins_list


def test_weak_secret_key_is_rejected():
    import pytest
    from pydantic import ValidationError

    config = importlib.import_module("app.config")
    for weak in ("", "secret", "a" * 40):
        with pytest.raises(ValidationError):
            config.Settings(MONGODB_URL="x", SECRET_KEY=weak)
