"""Alpaca adapter mapping. HTTP is mocked; no network and no real keys."""

import asyncio
import json
from decimal import Decimal

import httpx

from app.brokers.alpaca import PAPER_BASE_URL, AlpacaBroker
from app.brokers.base import BrokerError, OrderRequest, OrderSide, OrderType

KEY = "test-key"
SECRET = "test-secret"


def _order_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "order-1",
        "symbol": "AAPL",
        "side": "sell",
        "qty": "1",
        "type": "market",
        "status": "accepted",
        "filled_qty": "0",
        "time_in_force": "day",
        "limit_price": None,
        "position_intent": "sell_to_open",
    }
    payload.update(overrides)
    return payload


def _broker(handler: httpx.MockTransport) -> AlpacaBroker:
    return AlpacaBroker(KEY, SECRET, PAPER_BASE_URL, transport=handler)


def test_from_env_defaults_to_paper(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", KEY)
    monkeypatch.setenv("ALPACA_API_SECRET", SECRET)
    monkeypatch.delenv("ALPACA_BASE_URL", raising=False)
    broker = AlpacaBroker.from_env()
    assert broker.base_url == PAPER_BASE_URL
    assert broker.supports_short_selling() is True


def test_sell_short_is_sent_as_an_equity_sell() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        seen["key"] = request.headers.get("APCA-API-KEY-ID")
        seen["secret"] = request.headers.get("APCA-API-SECRET-KEY")
        return httpx.Response(200, json=_order_payload())

    broker = _broker(httpx.MockTransport(handler))

    async def run():
        return await broker.place_order(
            OrderRequest(
                symbol="AAPL",
                side=OrderSide.SELL_SHORT,
                qty=Decimal("1"),
                order_type=OrderType.MARKET,
            )
        )

    order = asyncio.run(run())
    assert seen["method"] == "POST"
    assert seen["path"] == "/v2/orders"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["side"] == "sell"
    assert body["symbol"] == "AAPL"
    assert body["type"] == "market"
    assert body["extended_hours"] is False
    assert "limit_price" not in body
    assert seen["key"] == KEY
    assert seen["secret"] == SECRET
    assert order.side is OrderSide.SELL_SHORT
    assert order.broker == "alpaca"


def test_buy_to_cover_is_sent_as_an_equity_buy() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json=_order_payload(side="buy", position_intent="buy_to_close", type="limit", limit_price="180"),
        )

    broker = _broker(httpx.MockTransport(handler))

    async def run():
        return await broker.place_order(
            OrderRequest(
                symbol="AAPL",
                side=OrderSide.BUY_TO_COVER,
                qty=Decimal("2"),
                order_type=OrderType.LIMIT,
                limit_price=Decimal("180"),
            )
        )

    order = asyncio.run(run())
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["side"] == "buy"
    assert body["limit_price"] == "180"
    assert order.side is OrderSide.BUY_TO_COVER
    assert order.limit_price == Decimal("180")


def test_extended_hours_is_sent_on_day_limit_orders() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json=_order_payload(
                side="buy",
                position_intent="buy_to_open",
                type="limit",
                limit_price="150",
                extended_hours=True,
            ),
        )

    broker = _broker(httpx.MockTransport(handler))
    order = asyncio.run(
        broker.place_order(
            OrderRequest(
                symbol="AAPL",
                side=OrderSide.BUY,
                qty=Decimal("1"),
                order_type=OrderType.LIMIT,
                limit_price=Decimal("150"),
                extended_hours=True,
            )
        )
    )
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["extended_hours"] is True
    assert body["type"] == "limit"
    assert body["time_in_force"] == "day"
    assert body["limit_price"] == "150"
    assert str(seen["url"]).startswith(PAPER_BASE_URL)
    assert order.extended_hours is True


def test_extended_hours_market_order_is_rejected() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("market extended-hours orders must not be sent")

    broker = _broker(httpx.MockTransport(handler))
    try:
        asyncio.run(
            broker.place_order(
                OrderRequest(
                    symbol="AAPL",
                    side=OrderSide.BUY,
                    qty=Decimal("1"),
                    order_type=OrderType.MARKET,
                    extended_hours=True,
                )
            )
        )
    except BrokerError as exc:
        assert exc.status_code == 400
        assert "extended-hours" in str(exc)
    else:
        raise AssertionError("expected BrokerError")


def test_cancel_deletes_then_marks_canceled() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json=_order_payload(status="accepted"))

    broker = _broker(httpx.MockTransport(handler))
    order = asyncio.run(broker.cancel_order("order-1"))
    assert methods == ["GET", "DELETE"]
    assert order.status == "canceled"


def test_get_quote_uses_latest_trade_price() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["host"] = request.url.host
        seen["path"] = request.url.path
        return httpx.Response(
            200,
            json={"symbol": "AAPL", "trade": {"p": 187.42, "s": 100, "t": "2024-01-01T15:00:00Z"}},
        )

    broker = _broker(httpx.MockTransport(handler))
    quote = asyncio.run(broker.get_quote("aapl"))
    assert seen["host"] == "data.alpaca.markets"
    assert seen["path"] == "/v2/stocks/AAPL/trades/latest"
    assert quote.symbol == "AAPL"
    assert quote.price == Decimal("187.42")
    assert quote.broker == "alpaca"


def test_positions_keep_short_sign() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "symbol": "TSLA",
                    "qty": "-4",
                    "avg_entry_price": "210.25",
                    "side": "short",
                    "current_price": "205.10",
                    "unrealized_pl": "20.60",
                }
            ],
        )

    broker = _broker(httpx.MockTransport(handler))
    positions = asyncio.run(broker.list_positions())
    assert positions[0].qty == Decimal("-4")
    assert positions[0].side == "short"
    assert positions[0].current_price == Decimal("205.10")
    assert positions[0].unrealized_pl == Decimal("20.60")


def test_alpaca_error_message_is_surfaced() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "insufficient buying power"})

    broker = _broker(httpx.MockTransport(handler))
    try:
        asyncio.run(
            broker.place_order(
                OrderRequest(
                    symbol="AAPL",
                    side=OrderSide.BUY,
                    qty=Decimal("1"),
                    order_type=OrderType.MARKET,
                )
            )
        )
    except Exception as exc:  # noqa: BLE001 - assert the broker error type below
        from app.brokers.base import BrokerError

        assert isinstance(exc, BrokerError)
        assert exc.status_code == 422
        assert "buying power" in str(exc)
    else:
        raise AssertionError("expected BrokerError")
