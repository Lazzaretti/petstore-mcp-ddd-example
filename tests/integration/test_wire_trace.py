import pytest

import wire_trace

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def exchanges(app_url: str) -> list[wire_trace.Exchange]:
    """One trace against fresh servers, like on the slide."""
    return wire_trace.trace(app_url)


def test_the_wire_trace_records_the_fixed_call_list(exchanges: list[wire_trace.Exchange]) -> None:
    assert [(e.path, e.method, e.name) for e in exchanges] == [
        ("/discovery/mcp", "server/discover", None),
        ("/discovery/mcp", "tools/list", None),
        ("/sales/mcp", "server/discover", None),
        ("/sales/mcp", "tools/list", None),
        ("/handover/mcp", "server/discover", None),
        ("/handover/mcp", "tools/list", None),
        ("/discovery/mcp", "tools/call", "find_available_pets"),
        ("/sales/mcp", "tools/call", "buy_pet"),
        ("/sales/mcp", "tools/call", "buy_pet"),
        ("/sales/mcp", "resources/read", "pet-sales://policies"),
    ]
    assert all(e.status == 200 for e in exchanges)


def test_requests_carry_the_2026_07_28_headers_and_meta(exchanges: list[wire_trace.Exchange]) -> None:
    call = exchanges[7]
    assert call.request_headers["Mcp-Method"] == "tools/call"
    assert call.request_headers["Mcp-Name"] == "buy_pet"
    assert call.request_headers["Mcp-Protocol-Version"] == "2026-07-28"
    assert call.request["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"


def test_the_second_purchase_of_the_same_pet_is_refused(exchanges: list[wire_trace.Exchange]) -> None:
    first_buy = exchanges[7].response["result"]
    assert first_buy["structuredContent"]["pet"] == "Rex"
    second_buy = exchanges[8].response["result"]
    assert second_buy["isError"] is True
    assert second_buy["content"][0]["text"].startswith("PetNotAvailable:")
