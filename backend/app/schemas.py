"""HTTP bodies for the order desk. These mirror BrokerInterface, not Alpaca."""

import re
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.brokers.base import (
    BrokerAccount,
    BrokerOrder,
    BrokerPosition,
    BrokerQuote,
    OrderSide,
    OrderType,
    TimeInForce,
)

_SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}")


def normalize_ticker(value: str) -> str:
    symbol = value.strip().upper()
    if not _SYMBOL.fullmatch(symbol):
        raise ValueError("symbol must be a ticker such as AAPL or BRK.B")
    return symbol


class PlaceOrderIn(BaseModel):
    symbol: str
    side: OrderSide
    qty: Decimal
    order_type: OrderType
    limit_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    extended_hours: bool = False

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_ticker(value)

    @field_validator("qty")
    @classmethod
    def qty_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("qty must be greater than zero")
        return value

    @model_validator(mode="after")
    def limit_price_rules(self) -> "PlaceOrderIn":
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit_price is required for limit orders")
            if self.limit_price <= 0:
                raise ValueError("limit_price must be greater than zero")
        return self


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    @classmethod
    def from_broker(cls, order: BrokerOrder) -> "OrderOut":
        return cls(
            id=order.id,
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            order_type=order.order_type,
            status=order.status,
            broker=order.broker,
            limit_price=order.limit_price,
            filled_qty=order.filled_qty,
            time_in_force=order.time_in_force,
            extended_hours=order.extended_hours,
        )


class AccountOut(BaseModel):
    id: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    shorting_enabled: bool
    broker: str

    @classmethod
    def from_broker(cls, account: BrokerAccount) -> "AccountOut":
        return cls(
            id=account.id,
            equity=account.equity,
            cash=account.cash,
            buying_power=account.buying_power,
            shorting_enabled=account.shorting_enabled,
            broker=account.broker,
        )


class QuoteOut(BaseModel):
    symbol: str
    price: Decimal
    broker: str

    @classmethod
    def from_broker(cls, quote: BrokerQuote) -> "QuoteOut":
        return cls(symbol=quote.symbol, price=quote.price, broker=quote.broker)


class PositionOut(BaseModel):
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    side: str
    broker: str
    current_price: Decimal | None = None
    unrealized_pl: Decimal | None = None

    @classmethod
    def from_broker(cls, position: BrokerPosition) -> "PositionOut":
        return cls(
            symbol=position.symbol,
            qty=position.qty,
            avg_entry_price=position.avg_entry_price,
            side=position.side,
            broker=position.broker,
            current_price=position.current_price,
            unrealized_pl=position.unrealized_pl,
        )
