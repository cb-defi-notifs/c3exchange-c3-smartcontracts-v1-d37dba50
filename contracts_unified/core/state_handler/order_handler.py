"""Defines the order book state handler for the core contract"""

from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    App,
    Assert,
    Bytes,
    Concat,
    Expr,
    If,
    Pop,
    Return,
    Seq,
    Sha512_256,
    abi,
)

from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.library.c3types import OnChainOrderData, OrderId
from contracts_unified.library.c3types_user import OrderData

ORDER_PREFIX = Bytes("order")


class OrderStateHandler:
    """Implements the order book state handler for the core contract"""

    @staticmethod
    @ABIReturnSubroutine
    def get_order_id(
        order: OrderData,
        *,
        output: OrderId,
    ) -> Expr:
        """Get the order ID for an order"""
        return output.set(Concat(ORDER_PREFIX, Sha512_256(order.encode())))

    @staticmethod
    @ABIReturnSubroutine
    def add_order(
        order: OrderData,
    ) -> Expr:
        """Adds an order to the order book"""

        order_id = abi.make(OrderId)
        on_chain_data = OnChainOrderData()

        return Seq(
            # Create order ID
            order_id.set(OrderStateHandler.get_order_id(order)),

            # Check order does not exist
            (length := App.box_length(order_id.get())),
            If(length.hasValue(), Return()),

            # Create on-chain data
            order.sell_amount.use(lambda sell_amount:
                order.max_borrow_amount.use(lambda borrow_amount:
                    order.max_repay_amount.use(lambda repay_amount:
                        on_chain_data.set(sell_amount, borrow_amount, repay_amount)
                    )
                )
            ),

            # Update box
            App.box_put(order_id.get(), on_chain_data.encode()),
            # Ensure we have enough funds for mbr
            cast(Expr, GlobalStateHandler.ensure_mbr_fund()),
        )

    @staticmethod
    @ABIReturnSubroutine
    def get_order_onchain(
        order_id: OrderId,
        *,
        output: OnChainOrderData,
    ) -> Expr:
        """Gets an order from the order book"""

        return Seq(
            (result := App.box_get(order_id.get())),
            Assert(result.hasValue()),
            output.decode(result.value()),
        )

    @staticmethod
    # NOTE: Not a subroutine for performance reasons
    # NOTE: We don't use this to create a box so there is no need to ensure the fund
    def set_order_onchain(
        order_id: OrderId,
        data: OnChainOrderData,
    ) -> Expr:
        """Sets an order in the order book"""
        return App.box_put(order_id.get(), data.encode())

    @staticmethod
    # NOTE: Not a subroutine for performance reasons
    def delete_order_onchain(
        order_id: OrderId,
    ) -> Expr:
        """Deletes an order from the order book"""
        return Pop(App.box_delete(order_id.get()))
