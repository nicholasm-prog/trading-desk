"""Order, account, and position routes.

Depends on BrokerInterface only. Alpaca and the TradeZero stub are selected
in the broker factory, not here.
"""

import os
from typing import Literal

from fastapi import APIRouter, HTTPException

from app.brokers.base import OrderRequest, OrderType
from app.deps import BrokerDep
from app.schemas import AccountOut, OrderOut, PlaceOrderIn, PositionOut, QuoteOut, normalize_ticker

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "broker": os.getenv("BROKER", "alpaca")}


@router.post("/orders", response_model=OrderOut, status_code=201)
async def place_order(body: PlaceOrderIn, broker: BrokerDep) -> OrderOut:
    request = OrderRequest(
        symbol=body.symbol,
        side=body.side,
        qty=body.qty,
        order_type=body.order_type,
        limit_price=body.limit_price if body.order_type is OrderType.LIMIT else None,
        time_in_force=body.time_in_force,
        extended_hours=body.extended_hours,
    )
    return OrderOut.from_broker(await broker.place_order(request))


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    broker: BrokerDep,
    status: Literal["open", "closed", "all"] = "open",
) -> list[OrderOut]:
    orders = await broker.list_orders(status=status)
    return [OrderOut.from_broker(order) for order in orders]


@router.delete("/orders/{order_id}", response_model=OrderOut)
async def cancel_order(order_id: str, broker: BrokerDep) -> OrderOut:
    return OrderOut.from_broker(await broker.cancel_order(order_id))


@router.get("/account", response_model=AccountOut)
async def get_account(broker: BrokerDep) -> AccountOut:
    return AccountOut.from_broker(await broker.get_account())


@router.get("/positions", response_model=list[PositionOut])
async def list_positions(broker: BrokerDep) -> list[PositionOut]:
    positions = await broker.list_positions()
    return [PositionOut.from_broker(position) for position in positions]


@router.get("/quotes/{symbol}", response_model=QuoteOut)
async def get_quote(symbol: str, broker: BrokerDep) -> QuoteOut:
    try:
        ticker = normalize_ticker(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuoteOut.from_broker(await broker.get_quote(ticker))
