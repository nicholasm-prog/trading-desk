"""TradeZero adapter stub.

Short selling is already part of BrokerInterface: supports_short_selling,
sell_short, and buy_to_cover. place_order dispatches those sides before the
HTTP layer cares which broker is configured.

Implement this class when TradeZero credentials and its locate / short-sale
API are ready. Order routes should keep depending on BrokerInterface only.
"""

from typing import NoReturn

from app.brokers.base import (
    BrokerAccount,
    BrokerInterface,
    BrokerNotImplemented,
    BrokerOrder,
    BrokerPosition,
    BrokerQuote,
    OrderRequest,
)


class TradeZeroBroker(BrokerInterface):
    """Reserved adapter for short selling. Every call returns HTTP 501."""

    @property
    def name(self) -> str:
        return "tradezero"

    def supports_short_selling(self) -> bool:
        return True

    async def submit_order(self, request: OrderRequest) -> BrokerOrder:
        self._unavailable()

    async def sell_short(self, request: OrderRequest) -> BrokerOrder:
        self._unavailable()

    async def buy_to_cover(self, request: OrderRequest) -> BrokerOrder:
        self._unavailable()

    async def list_orders(self, status: str | None = "open") -> list[BrokerOrder]:
        self._unavailable()

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        self._unavailable()

    async def get_account(self) -> BrokerAccount:
        self._unavailable()

    async def list_positions(self) -> list[BrokerPosition]:
        self._unavailable()

    async def get_quote(self, symbol: str) -> BrokerQuote:
        self._unavailable()

    def _unavailable(self) -> NoReturn:
        raise BrokerNotImplemented(
            "TradeZero is not implemented yet. Short sales will land in this "
            "adapter (locate, sell_short, and buy_to_cover) without changing "
            "the order API."
        )
