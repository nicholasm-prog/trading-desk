"""FastAPI dependencies. Routes ask for BrokerInterface, not a concrete adapter."""

from typing import Annotated

from fastapi import Depends

from app.brokers import BrokerInterface, create_broker


def get_broker() -> BrokerInterface:
    return create_broker()


BrokerDep = Annotated[BrokerInterface, Depends(get_broker)]
