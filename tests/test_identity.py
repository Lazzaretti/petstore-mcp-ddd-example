import pytest

from petstore import identity


def test_auth_off_takes_the_customer_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PETSTORE_CUSTOMER", "bob")
    assert identity.current_customer() == "bob"


def test_auth_off_has_no_auth_provider() -> None:
    assert identity.auth_provider("sales") is None


def test_auth_on_verifies_audience_and_scope_per_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH", "on")
    provider = identity.auth_provider("sales")
    assert provider is not None
    verifier = provider.token_verifier
    assert verifier.audience == "http://localhost:8000/sales/mcp"
    assert verifier.required_scopes == ["petstore:sales"]
    assert verifier.issuer == "http://localhost:8080/realms/petstore"


def test_auth_on_without_a_token_refuses_to_guess_the_customer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH", "on")
    with pytest.raises(identity.NotSignedIn):
        identity.current_customer()
