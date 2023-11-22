"""
Clean any expired orders from the order book
"""

from typing import cast

from pyteal import ABIReturnSubroutine, Expr, For, Global, If, Int, Seq, abi

from contracts_unified.core.state_handler.order_handler import OrderStateHandler
from contracts_unified.library.c3types import OrderId
from contracts_unified.library.c3types_user import OrderData


@ABIReturnSubroutine
def clean_orders(
    orders: abi.DynamicArray[OrderData],
) -> Expr:
    """
    Clean any expired orders from the order book

    Arguments:

    orders: The orders to analyze.
    """

    i = abi.Uint64()
    length = abi.Uint64()
    order_data = OrderData()
    order_id = abi.make(OrderId)

    return Seq(
        # Loop through all orders
        length.set(orders.length()),
        For(i.set(Int(0)), i.get() < length.get(), i.set(i.get() + Int(1))).Do(
            # Check if order is expired
            order_data.set(orders[i.get()]),
            order_data.expiration_time.use(lambda expires:
                If(Global.latest_timestamp() > expires.get())
                .Then(
                    # Delete order
                    order_id.set(cast(abi.ReturnedValue, OrderStateHandler.get_order_id(order_data))),
                    cast(Expr, OrderStateHandler.delete_order_onchain(order_id)),
                )
            ),
        ),
    )
