"""Alpaca equity adapter.

Paper trading is the default base URL. Short entry and cover are part of the
shared interface: Alpaca has no separate short side, so sell_short is sent as
an equity sell and buy_to_cover is sent as an equity buy. A short opens only
when the Alpaca account has shorting enabled. TradeZero is the later home for
a native short-sale flow.
"""

import os
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

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
    TimeInForce,
)

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
DATA_BASE_URL = "https://data.alpaca.markets"

_SIDE_TO_ALPACA = {
    OrderSide.BUY: "buy",
    OrderSide.BUY_TO_COVER: "buy",
    OrderSide.SELL: "sell",
    OrderSide.SELL_SHORT: "sell",
}


def _decimal(value: object, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise BrokerError("Alpaca returned a non-numeric amount", 502) from exc


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return _decimal(value)


class AlpacaBroker(BrokerInterface):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        data_base_url: str = DATA_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self._data_base_url = data_base_url.rstrip("/")
        self._transport = transport

    @classmethod
    def from_env(cls) -> "AlpacaBroker":
        api_key = os.getenv("ALPACA_API_KEY", "").strip()
        api_secret = os.getenv("ALPACA_API_SECRET", "").strip()
        base_url = os.getenv("ALPACA_BASE_URL", PAPER_BASE_URL).strip() or PAPER_BASE_URL
        if not api_key or not api_secret:
            raise BrokerError(
                "Alpaca credentials are missing. Set ALPACA_API_KEY and ALPACA_API_SECRET.",
                status_code=503,
            )
        if not base_url.startswith("https://"):
            raise BrokerError("ALPACA_BASE_URL must start with https://", status_code=500)
        return cls(api_key=api_key, api_secret=api_secret, base_url=base_url)

    @property
    def name(self) -> str:
        return "alpaca"

    def supports_short_selling(self) -> bool:
        # The equity API can open shorts. The account flag shorting_enabled
        # decides whether this particular account is allowed to.
        return True

    async def submit_order(self, request: OrderRequest) -> BrokerOrder:
        if request.side in (OrderSide.SELL_SHORT, OrderSide.BUY_TO_COVER):
            raise BrokerError(
                "Use sell_short or buy_to_cover for short orders.",
                status_code=400,
            )
        return await self._submit(request)

    async def sell_short(self, request: OrderRequest) -> BrokerOrder:
        # Equity short: Alpaca treats this as a sell. TradeZero replaces this method.
        return await self._submit(request)

    async def buy_to_cover(self, request: OrderRequest) -> BrokerOrder:
        # Cover: Alpaca treats this as a buy. TradeZero replaces this method.
        return await self._submit(request)

    async def list_orders(self, status: str | None = "open") -> list[BrokerOrder]:
        response = await self._request(
            "GET",
            "/v2/orders",
            params={
                "status": status or "open",
                "limit": 50,
                "direction": "desc",
                "nested": "false",
            },
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise BrokerError("Alpaca returned an unexpected order list", 502)
        return [self._parse_order(item) for item in payload]

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        current = await self._get_order(order_id)
        await self._request("DELETE", f"/v2/orders/{order_id}")
        return BrokerOrder(
            id=current.id,
            symbol=current.symbol,
            side=current.side,
            qty=current.qty,
            order_type=current.order_type,
            status="canceled",
            broker=self.name,
            limit_price=current.limit_price,
            filled_qty=current.filled_qty,
            time_in_force=current.time_in_force,
            extended_hours=current.extended_hours,
        )

    async def get_account(self) -> BrokerAccount:
        payload = (await self._request("GET", "/v2/account")).json()
        if not isinstance(payload, dict):
            raise BrokerError("Alpaca returned an unexpected account payload", 502)
        return BrokerAccount(
            id=str(payload.get("id") or payload.get("account_number") or ""),
            equity=_decimal(payload.get("equity")),
            cash=_decimal(payload.get("cash")),
            buying_power=_decimal(payload.get("buying_power")),
            shorting_enabled=bool(payload.get("shorting_enabled")),
            broker=self.name,
        )

    async def list_positions(self) -> list[BrokerPosition]:
        payload = (await self._request("GET", "/v2/positions")).json()
        if not isinstance(payload, list):
            raise BrokerError("Alpaca returned an unexpected position list", 502)
        return [self._parse_position(item) for item in payload]

    async def get_quote(self, symbol: str) -> BrokerQuote:
        ticker = symbol.strip().upper()
        payload = (
            await self._request(
                "GET",
                f"/v2/stocks/{ticker}/trades/latest",
                base_url=self._data_base_url,
            )
        ).json()
        if not isinstance(payload, dict):
            raise BrokerError("Alpaca returned an unexpected quote payload", 502)
        trade = payload.get("trade")
        if not isinstance(trade, dict):
            raise BrokerError(f"No market data for {ticker}", 404)
        price = _optional_decimal(trade.get("p"))
        if price is None:
            raise BrokerError(f"No market data for {ticker}", 404)
        return BrokerQuote(symbol=ticker, price=price, broker=self.name)

    async def _get_order(self, order_id: str) -> BrokerOrder:
        payload = (await self._request("GET", f"/v2/orders/{order_id}")).json()
        if not isinstance(payload, dict):
            raise BrokerError("Alpaca returned an unexpected order payload", 502)
        return self._parse_order(payload)

    async def _submit(self, request: OrderRequest) -> BrokerOrder:
        if request.extended_hours and (
            request.order_type is not OrderType.LIMIT or request.time_in_force is not TimeInForce.DAY
        ):
            raise BrokerError(
                "Alpaca extended-hours orders must be day limit orders.",
                status_code=400,
            )
        body: dict[str, str | bool] = {
            "symbol": request.symbol,
            "qty": format(request.qty, "f"),
            "side": _SIDE_TO_ALPACA[request.side],
            "type": request.order_type.value,
            "time_in_force": request.time_in_force.value,
            "extended_hours": request.extended_hours,
        }
        if request.order_type is OrderType.LIMIT:
            if request.limit_price is None:
                raise BrokerError("limit_price is required for limit orders", 400)
            body["limit_price"] = format(request.limit_price, "f")
        payload = (await self._request("POST", "/v2/orders", json=body)).json()
        if not isinstance(payload, dict):
            raise BrokerError("Alpaca returned an unexpected order payload", 502)
        return self._parse_order(payload, requested_side=request.side)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, str | bool] | None = None,
        params: dict[str, str | int] | None = None,
        base_url: str | None = None,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=base_url or self.base_url,
                headers={
                    "APCA-API-KEY-ID": self._api_key,
                    "APCA-API-SECRET-KEY": self._api_secret,
                },
                transport=self._transport,
                timeout=20.0,
            ) as client:
                response = await client.request(method, path, json=json, params=params)
        except httpx.HTTPError as exc:
            raise BrokerError("Could not reach Alpaca", 502) from exc
        if response.status_code >= 400:
            status = 502 if response.status_code >= 500 else response.status_code
            raise BrokerError(_error_message(response), status)
        return response

    def _parse_order(
        self,
        payload: dict[str, Any],
        requested_side: OrderSide | None = None,
    ) -> BrokerOrder:
        raw_type = str(payload.get("type") or payload.get("order_type") or "market").lower()
        order_type = OrderType.LIMIT if raw_type == "limit" else OrderType.MARKET
        raw_tif = str(payload.get("time_in_force") or "day").lower()
        time_in_force = TimeInForce.GTC if raw_tif == "gtc" else TimeInForce.DAY
        return BrokerOrder(
            id=str(payload.get("id") or ""),
            symbol=str(payload.get("symbol") or ""),
            side=_side_from_payload(payload, requested_side),
            qty=_decimal(payload.get("qty")),
            order_type=order_type,
            status=str(payload.get("status") or "unknown").lower(),
            broker=self.name,
            limit_price=_optional_decimal(payload.get("limit_price")),
            filled_qty=_decimal(payload.get("filled_qty")),
            time_in_force=time_in_force,
            extended_hours=bool(payload.get("extended_hours")),
        )

    def _parse_position(self, payload: dict[str, Any]) -> BrokerPosition:
        qty = _decimal(payload.get("qty"))
        side = str(payload.get("side") or ("short" if qty < 0 else "long"))
        return BrokerPosition(
            symbol=str(payload.get("symbol") or ""),
            qty=qty,
            avg_entry_price=_decimal(payload.get("avg_entry_price")),
            side=side,
            broker=self.name,
            current_price=_optional_decimal(payload.get("current_price")),
            unrealized_pl=_optional_decimal(payload.get("unrealized_pl")),
        )


def _side_from_payload(payload: dict[str, Any], requested_side: OrderSide | None) -> OrderSide:
    intent = str(payload.get("position_intent") or "").lower()
    if intent == "sell_to_open":
        return OrderSide.SELL_SHORT
    if intent == "buy_to_close":
        return OrderSide.BUY_TO_COVER
    if intent == "buy_to_open":
        return OrderSide.BUY
    if intent == "sell_to_close":
        return OrderSide.SELL
    if requested_side is not None:
        return requested_side
    if str(payload.get("side") or "").lower() == "buy":
        return OrderSide.BUY
    return OrderSide.SELL


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("detail")
        if isinstance(message, str) and message.strip():
            return message.strip()
    text = response.text.strip()
    if text:
        return text[:500]
    return f"Alpaca request failed ({response.status_code})"
