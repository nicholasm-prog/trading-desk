"""Order routes depend on BrokerInterface. These tests never call Alpaca."""

from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.brokers.base import (
    BrokerAccount,
    BrokerError,
    BrokerInterface,
    BrokerOrder,
    BrokerPosition,
    BrokerQuote,
    OrderRequest,
    OrderSide,
    OrderType,
)
from app.deps import get_broker
from app.main import app

OPEN_STATUSES = {"new", "accepted", "partially_filled", "pending_cancel"}


class FakeBroker(BrokerInterface):
    def __init__(self, shorting: bool = True) -> None:
        self._shorting = shorting
        self.orders: dict[str, BrokerOrder] = {}

    @property
    def name(self) -> str:
        return "fake"

    def supports_short_selling(self) -> bool:
        return self._shorting

    async def submit_order(self, request: OrderRequest) -> BrokerOrder:
        return self._save(request)

    async def sell_short(self, request: OrderRequest) -> BrokerOrder:
        return self._save(replace(request, side=OrderSide.SELL_SHORT))

    async def buy_to_cover(self, request: OrderRequest) -> BrokerOrder:
        return self._save(replace(request, side=OrderSide.BUY_TO_COVER))

    async def list_orders(self, status: str | None = "open") -> list[BrokerOrder]:
        orders = list(self.orders.values())
        if status in (None, "all"):
            return orders
        if status == "open":
            return [order for order in orders if order.status in OPEN_STATUSES]
        if status == "closed":
            return [order for order in orders if order.status not in OPEN_STATUSES]
        return orders

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        order = self.orders.get(order_id)
        if order is None:
            raise BrokerError("Order not found", 404)
        if order.status not in OPEN_STATUSES:
            raise BrokerError(f"Order is {order.status} and cannot be canceled", 400)
        updated = replace(order, status="canceled")
        self.orders[order_id] = updated
        return updated

    async def get_account(self) -> BrokerAccount:
        return BrokerAccount(
            id="paper-1",
            equity=Decimal("100000"),
            cash=Decimal("100000"),
            buying_power=Decimal("200000"),
            shorting_enabled=self._shorting,
            broker=self.name,
        )

    async def list_positions(self) -> list[BrokerPosition]:
        return [
            BrokerPosition(
                symbol="AAPL",
                qty=Decimal("-2"),
                avg_entry_price=Decimal("190"),
                side="short",
                broker=self.name,
                current_price=Decimal("185.50"),
                unrealized_pl=Decimal("9"),
            )
        ]

    async def get_quote(self, symbol: str) -> BrokerQuote:
        return BrokerQuote(
            symbol=symbol.strip().upper(),
            price=Decimal("187.25"),
            broker=self.name,
        )

    def _save(self, request: OrderRequest) -> BrokerOrder:
        order = BrokerOrder(
            id=uuid4().hex,
            symbol=request.symbol,
            side=request.side,
            qty=request.qty,
            order_type=request.order_type,
            status="accepted",
            broker=self.name,
            limit_price=request.limit_price,
            filled_qty=Decimal("0"),
            time_in_force=request.time_in_force,
            extended_hours=request.extended_hours,
        )
        self.orders[order.id] = order
        return order


def _client_for(broker: BrokerInterface) -> TestClient:
    app.dependency_overrides[get_broker] = lambda: broker
    return TestClient(app)


def setup_function() -> None:
    app.dependency_overrides.clear()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_list_closed_orders_includes_filled_and_canceled() -> None:
    broker = FakeBroker()
    client = _client_for(broker)

    placed = client.post(
        "/api/orders",
        json={"symbol": "MSFT", "side": "sell_short", "qty": "2", "order_type": "market"},
    )
    assert placed.status_code == 201
    filled_id = placed.json()["id"]
    broker.orders[filled_id] = replace(broker.orders[filled_id], status="filled", filled_qty=Decimal("2"))

    canceled = client.post(
        "/api/orders",
        json={"symbol": "AAPL", "side": "buy", "qty": "1", "order_type": "market"},
    )
    assert canceled.status_code == 201
    cancel_id = canceled.json()["id"]
    client.delete(f"/api/orders/{cancel_id}")

    closed = client.get("/api/orders", params={"status": "closed"})
    assert closed.status_code == 200
    by_id = {order["id"]: order for order in closed.json()}
    assert by_id[filled_id]["status"] == "filled"
    assert by_id[filled_id]["filled_qty"] == "2"
    assert by_id[cancel_id]["status"] == "canceled"
    assert client.get("/api/orders").json() == []


def test_place_list_and_cancel_order() -> None:
    broker = FakeBroker()
    client = _client_for(broker)

    placed = client.post(
        "/api/orders",
        json={"symbol": "aapl", "side": "buy", "qty": "1", "order_type": "market"},
    )
    assert placed.status_code == 201
    body = placed.json()
    assert body["symbol"] == "AAPL"
    assert body["side"] == "buy"
    assert body["qty"] == "1"
    assert body["status"] == "accepted"
    assert body["broker"] == "fake"

    listed = client.get("/api/orders")
    assert listed.status_code == 200
    assert [order["id"] for order in listed.json()] == [body["id"]]

    canceled = client.delete(f"/api/orders/{body['id']}")
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert client.get("/api/orders").json() == []


def test_sell_short_uses_the_short_method() -> None:
    broker = FakeBroker()
    client = _client_for(broker)
    response = client.post(
        "/api/orders",
        json={
            "symbol": "TSLA",
            "side": "sell_short",
            "qty": "3",
            "order_type": "limit",
            "limit_price": "250.5",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["side"] == "sell_short"
    assert body["order_type"] == "limit"
    assert body["limit_price"] == "250.5"
    assert body["extended_hours"] is False


def test_extended_hours_round_trip() -> None:
    client = _client_for(FakeBroker())
    response = client.post(
        "/api/orders",
        json={
            "symbol": "AAPL",
            "side": "buy",
            "qty": "1",
            "order_type": "limit",
            "limit_price": "150",
            "extended_hours": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["extended_hours"] is True


def test_broker_without_shorts_rejects_sell_short() -> None:
    client = _client_for(FakeBroker(shorting=False))
    response = client.post(
        "/api/orders",
        json={"symbol": "TSLA", "side": "sell_short", "qty": "1", "order_type": "market"},
    )
    assert response.status_code == 400
    assert "short" in response.json()["detail"].lower()


def test_limit_order_requires_a_price() -> None:
    client = _client_for(FakeBroker())
    response = client.post(
        "/api/orders",
        json={"symbol": "AAPL", "side": "buy", "qty": "1", "order_type": "limit"},
    )
    assert response.status_code == 422


def test_get_quote_for_valid_ticker() -> None:
    client = _client_for(FakeBroker())
    response = client.get("/api/quotes/aapl")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["price"] == "187.25"
    assert body["broker"] == "fake"


def test_get_quote_rejects_invalid_ticker() -> None:
    client = _client_for(FakeBroker())
    response = client.get("/api/quotes/!!!")
    assert response.status_code == 422


def test_account_and_positions() -> None:
    client = _client_for(FakeBroker())
    account = client.get("/api/account")
    assert account.status_code == 200
    assert account.json()["shorting_enabled"] is True
    positions = client.get("/api/positions")
    assert positions.status_code == 200
    assert positions.json()[0]["side"] == "short"
    assert positions.json()[0]["qty"] == "-2"
    assert positions.json()[0]["current_price"] == "185.50"
    assert positions.json()[0]["unrealized_pl"] == "9"


def test_missing_alpaca_keys_are_a_service_error(monkeypatch) -> None:
    monkeypatch.setenv("BROKER", "alpaca")
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
    response = TestClient(app).post(
        "/api/orders",
        json={"symbol": "AAPL", "side": "buy", "qty": "1", "order_type": "market"},
    )
    assert response.status_code == 503
    assert "ALPACA_API_KEY" in response.json()["detail"]


def test_tradezero_stub_is_not_implemented(monkeypatch) -> None:
    monkeypatch.setenv("BROKER", "tradezero")
    response = TestClient(app).post(
        "/api/orders",
        json={"symbol": "AAPL", "side": "sell_short", "qty": "1", "order_type": "market"},
    )
    assert response.status_code == 501
    detail = response.json()["detail"].lower()
    assert "tradezero" in detail
    assert "sell_short" in detail


def test_env_example_has_empty_secrets() -> None:
    from app.config import BACKEND_ROOT

    text = (BACKEND_ROOT / ".env.example").read_text()
    values = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    assert values["ALPACA_API_KEY"] == ""
    assert values["ALPACA_API_SECRET"] == ""
    assert values["ALPACA_BASE_URL"] == "https://paper-api.alpaca.markets"
