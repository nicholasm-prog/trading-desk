"""Swappable broker adapters.

API routes depend on BrokerInterface. Import that type from this package
instead of constructing an Alpaca client in the route layer.
"""

from app.brokers.base import (
    BrokerAccount,
    BrokerError,
    BrokerInterface,
    BrokerNotImplemented,
    BrokerOrder,
    BrokerPosition,
    OrderRequest,
    OrderSide,
    OrderType,
    TimeInForce,
)
from app.brokers.factory import create_broker

__all__ = [
    "BrokerAccount",
    "BrokerError",
    "BrokerInterface",
    "BrokerNotImplemented",
    "BrokerOrder",
    "BrokerPosition",
    "OrderRequest",
    "OrderSide",
    "OrderType",
    "TimeInForce",
    "create_broker",
]
