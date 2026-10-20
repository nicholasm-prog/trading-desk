"""Build the broker named by the BROKER environment variable."""

import os

from app.brokers.alpaca import AlpacaBroker
from app.brokers.base import BrokerError, BrokerInterface
from app.brokers.tradezero import TradeZeroBroker


def create_broker() -> BrokerInterface:
    """Return the configured adapter. Routes call this via FastAPI Depends."""
    name = os.getenv("BROKER", "alpaca").strip().lower() or "alpaca"
    if name == "alpaca":
        return AlpacaBroker.from_env()
    if name == "tradezero":
        return TradeZeroBroker()
    raise BrokerError(
        f"Unknown broker '{name}'. Use 'alpaca' or 'tradezero'.",
        status_code=500,
    )
