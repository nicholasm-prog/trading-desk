"""Broker contract shared by every adapter.

Short sales are part of the contract (sell_short / buy_to_cover) so a later
TradeZero adapter can implement them without changing the HTTP API.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    SELL_SHORT = "sell_short"
    BUY_TO_COVER = "buy_to_cover"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"


class BrokerError(Exception):
    """Expected broker failure that should surface as an HTTP error."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class BrokerNotImplemented(BrokerError):
    """Raised by adapters that are extension points, not live brokers."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=501)


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: OrderSide
    qty: Decimal
    order_type: OrderType
    limit_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    # Pre-market and after-hours. Alpaca accepts this on day limit orders.
    extended_hours: bool = False


@dataclass(frozen=True)
class BrokerOrder:
    id: str
    symbol: str
    side: OrderSide
    qty: Decimal
    order_type: OrderType
    status: str
    broker: str
    limit_price: Decimal | None = None
    filled_qty: Decimal = Decimal("0")
    time_in_force: TimeInForce = TimeInForce.DAY
    extended_hours: bool = False


@dataclass(frozen=True)
class BrokerAccount:
    id: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    shorting_enabled: bool
    broker: str


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    side: str
    broker: str
    current_price: Decimal | None = None
    unrealized_pl: Decimal | None = None


@dataclass(frozen=True)
class BrokerQuote:
    symbol: str
    price: Decimal
    broker: str


_SHORT_SIDES = frozenset({OrderSide.SELL_SHORT, OrderSide.BUY_TO_COVER})


class BrokerInterface(ABC):
    """Order, account, and position operations every broker must provide."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable adapter name, such as 'alpaca' or 'tradezero'."""

    @abstractmethod
    def supports_short_selling(self) -> bool:
        """Whether this broker can open and cover short stock positions."""

    async def place_order(self, request: OrderRequest) -> BrokerOrder:
        """Place an order, dispatching short sides to the short methods.

        Routes call this method. They do not need to know which adapter is live.
        """
        if request.side in _SHORT_SIDES and not self.supports_short_selling():
            raise BrokerError(
                f"{self.name} does not support short selling",
                status_code=400,
            )
        if request.side is OrderSide.SELL_SHORT:
            return await self.sell_short(replace(request, side=OrderSide.SELL_SHORT))
        if request.side is OrderSide.BUY_TO_COVER:
            return await self.buy_to_cover(replace(request, side=OrderSide.BUY_TO_COVER))
        return await self.submit_order(request)

    @abstractmethod
    async def submit_order(self, request: OrderRequest) -> BrokerOrder:
        """Submit a buy or sell that is not a short-sale lifecycle order."""

    @abstractmethod
    async def sell_short(self, request: OrderRequest) -> BrokerOrder:
        """Open a short position.

        TradeZero should implement locates and the short sale here.
        """

    @abstractmethod
    async def buy_to_cover(self, request: OrderRequest) -> BrokerOrder:
        """Buy to cover an open short."""

    @abstractmethod
    async def list_orders(self, status: str | None = "open") -> list[BrokerOrder]:
        """Return orders. status is 'open', 'closed', or 'all'."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> BrokerOrder:
        """Cancel a working order and return its resulting state."""

    @abstractmethod
    async def get_account(self) -> BrokerAccount:
        """Return balances, including whether the account may short."""

    @abstractmethod
    async def list_positions(self) -> list[BrokerPosition]:
        """Return open positions. Negative qty is a short."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> BrokerQuote:
        """Return a latest market price for a ticker."""
