import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def auth_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit and contract tests run like `tools` and `demo`: AUTH=off, alice by default."""
    monkeypatch.setenv("AUTH", "off")
    monkeypatch.setenv("PETSTORE_CUSTOMER", "alice")
