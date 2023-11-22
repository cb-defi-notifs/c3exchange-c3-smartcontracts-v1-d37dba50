"""
Implements Core contract method for settling a pair of orders.
"""
from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    And,
    Assert,
    BytesGe,
    BytesMul,
    Expr,
    Global,
    If,
    Int,
    Itob,
    MethodSignature,
    Not,
    OnComplete,
    Or,
    Seq,
    abi,
)

from contracts_unified.core.c3call import (
    ARG_INDEX_ACCOUNT,
    ARG_INDEX_OP,
    ARG_INDEX_SELECTOR,
)
from contracts_unified.core.internal.health_check import health_check
from contracts_unified.core.internal.move import collect_fees, signed_add_to_cash
from contracts_unified.core.internal.perform_pool_move import perform_pool_move
from contracts_unified.core.internal.setup import setup
from contracts_unified.core.internal.validate_sender import sender_is_sig_validator
from contracts_unified.core.state_handler.order_handler import OrderStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    Boolean,
    ExcessMargin,
    InstrumentId,
    OnChainOrderData,
    OrderId,
    SignedAmount,
)
from contracts_unified.library.c3types_server import SettleExtraData
from contracts_unified.library.c3types_user import (
    DelegationChain,
    OperationId,
    OperationMetaData,
    OrderData,
)
from contracts_unified.library.signed_math import signed_gte, signed_ltz, signed_neg

ADD_ORDER_SIG = MethodSignature("add_order(address,((address,byte[32],uint64),byte[],byte[],uint8,byte[],address,byte[]),((address,byte[32],uint64),byte[],byte[],uint8,byte[],address,byte[])[],uint64)void")
ADD_ORDER_ARG_COUNT = Int(5)
MAX_FEES_DIVISOR = Int(40)

@ABIReturnSubroutine
def add_order(
    # NOTE: Any update on this function must update ADD_ORDER_SIG and ADD_ORDER_ARG_COUNT above
    account: AccountAddress,
    user_op: OperationMetaData,
    _delegation_chain: DelegationChain,
    opup_budget: Amount,
) -> Expr:

    """Adds an order to the order book

    Arguments:

    account (AccountAddress): User's account address.
    user_op (OperationMetaData): Operation metadata containing order data.
    _delegation_chain (DelegationChain): Delegation chain.  Unused.
    opup_budget (Amount): Additional computation budget to allocate to this transaction.

    """

    order = OrderData()

    return Seq(
        setup(opup_budget.get()),

        # Validate signature validator' call
        cast(Expr, sender_is_sig_validator()),

        # Get order from user_op.data
        user_op.operation.use(lambda op_data:
            Seq(
                order.decode(op_data.get()),
                order.operation.use(lambda op: Assert(op.get() == OperationId.Settle)),
                order.account.use(lambda acc: Assert(acc.get() == account.get()))
            )
        ),

        # Add order to the order book
        cast(Expr, OrderStateHandler.add_order(order))
    )


@ABIReturnSubroutine
def settle(
    add_order_txn: abi.ApplicationCallTransaction,
    buy_account: AccountAddress,
    user_op: OperationMetaData,
    _delegation_chain: DelegationChain,
    server_args: SettleExtraData,
    opup_budget: Amount,
) -> Expr:
    """Settles two orders

    Arguments:

    add_order_txn (ApplicationCallTransaction): The previous add_order transaction in this group that added the sell order to the order book.
    buy_account (AccountAddress): The buyer user's account address.
    user_op (OperationMetaData): Operation metadata containing buyer order data.
    _delegation_chain (DelegationChain): Delegation chain.  Unused.
    server_args (SettleExtraData): Extra data for the settle operation.
    opup_budget (Amount): Additional computation budget to allocate to this transaction.

    """

    abi_false = abi.Bool()
    add_order_op = OperationMetaData()
    add_order_data = abi.make(abi.DynamicBytes)

    buy_order = OrderData()
    sell_order = OrderData()

    sell_account = AccountAddress()

    buy_order_id = abi.make(OrderId)
    sell_order_id = abi.make(OrderId)

    buy_order_onchain = OnChainOrderData()
    sell_order_onchain = OnChainOrderData()

    # Amounts for each order's buy/sell side
    buyer_sell_amount = Amount()
    buyer_buy_amount = Amount()
    seller_sell_amount = Amount()
    seller_buy_amount = Amount()

    # Remaining amounts for each order's buy/sell side
    buyer_sell_remaining = Amount()
    buyer_borrow_remaining = Amount()
    buyer_repay_remaining = Amount()

    seller_sell_remaining = Amount()
    seller_borrow_remaining = Amount()
    seller_repay_remaining = Amount()

    # New remaining amounts for each order's buy/sell side
    buyer_new_sell_remaining = Amount()
    buyer_new_borrow_remaining = Amount()
    buyer_new_repay_remaining = Amount()

    seller_new_sell_remaining = Amount()
    seller_new_borrow_remaining = Amount()
    seller_new_repay_remaining = Amount()

    buyer_new_order_onchain = OnChainOrderData()
    seller_new_order_onchain = OnChainOrderData()

    buyer_buy_instrument = InstrumentId()
    buyer_sell_instrument = InstrumentId()
    seller_buy_instrument = InstrumentId()
    seller_sell_instrument = InstrumentId()

    buyer_to_send = Amount()
    seller_to_send = Amount()

    buyer_to_borrow = Amount()
    seller_to_borrow = Amount()
    buyer_to_repay = Amount()
    seller_to_repay = Amount()

    buyer_buy_delta = Amount()
    seller_buy_delta = Amount()
    buyer_sell_delta = Amount()
    seller_sell_delta = Amount()

    neg_borrow = SignedAmount()

    buyer_fees = Amount()
    seller_fees = Amount()

    buyer_old_health = ExcessMargin()
    buyer_health = ExcessMargin()
    seller_old_health = ExcessMargin()
    seller_health = ExcessMargin()

    buyer_negative_margin = Boolean()
    seller_negative_margin = Boolean()

    return Seq(
        setup(opup_budget.get()),

        # Set constants
        abi_false.set(Int(0)),

        # Validate sender is a user proxy
        cast(Expr, sender_is_sig_validator()),

        # Extract the buy order
        user_op.operation.use(lambda op_data:
            Seq(
                buy_order.decode(op_data.get()),
                buy_order.operation.use(lambda op: Assert(op.get() == OperationId.Settle)),
                buy_order.account.use(lambda acc: Assert(acc.get() == buy_account.get())),
            )
        ),

        # Add the order to the order book
        cast(Expr, OrderStateHandler.add_order(buy_order)),

        # Validate the sell order
        Assert(add_order_txn.get().application_id() == Global.current_application_id()),
        Assert(add_order_txn.get().on_completion() == OnComplete.NoOp),
        Assert(add_order_txn.get().application_args.length() == ADD_ORDER_ARG_COUNT),
        Assert(add_order_txn.get().application_args[ARG_INDEX_SELECTOR] == ADD_ORDER_SIG),

        # Get the sell order
        sell_account.decode(add_order_txn.get().application_args[ARG_INDEX_ACCOUNT]),
        add_order_op.decode(add_order_txn.get().application_args[ARG_INDEX_OP]),
        add_order_op.operation.store_into(add_order_data),
        sell_order.decode(add_order_data.get()),

        # Get order IDs
        buy_order_id.set(OrderStateHandler.get_order_id(buy_order)),
        sell_order_id.set(OrderStateHandler.get_order_id(sell_order)),

        # Get on chain order data
        buy_order_onchain.set(cast(abi.ReturnedValue, OrderStateHandler.get_order_onchain(buy_order_id))),
        sell_order_onchain.set(cast(abi.ReturnedValue, OrderStateHandler.get_order_onchain(sell_order_id))),

        # Validate the asset pair matches
        buy_order.sell_instrument.store_into(buyer_sell_instrument),
        buy_order.buy_instrument.store_into(buyer_buy_instrument),
        sell_order.sell_instrument.store_into(seller_sell_instrument),
        sell_order.buy_instrument.store_into(seller_buy_instrument),

        Assert(buyer_sell_instrument.get() == seller_buy_instrument.get()),
        Assert(buyer_buy_instrument.get() == seller_sell_instrument.get()),

        # Validate the orders are not expired
        buy_order.expiration_time.use(lambda expiration_time:
            Assert(expiration_time.get() > Global.latest_timestamp())
        ),
        sell_order.expiration_time.use(lambda expiration_time:
            Assert(expiration_time.get() > Global.latest_timestamp())
        ),

        # Validate the orders match
        buyer_sell_amount.set(buy_order.sell_amount),
        buyer_buy_amount.set(buy_order.buy_amount),
        seller_sell_amount.set(sell_order.sell_amount),
        seller_buy_amount.set(sell_order.buy_amount),

        Assert(
            BytesGe(
                BytesMul(Itob(buyer_sell_amount.get()), Itob(seller_sell_amount.get())),
                BytesMul(Itob(buyer_buy_amount.get()), Itob(seller_buy_amount.get()))
            )
        ),

        # Validate that the swap is fair for both the seller and the buyer
        buyer_to_send.set(server_args.buyer_to_send),
        seller_to_send.set(server_args.seller_to_send),

        Assert(
            BytesGe(
                BytesMul(Itob(buyer_to_send.get()), Itob(seller_sell_amount.get())),
                BytesMul(Itob(seller_to_send.get()), Itob(seller_buy_amount.get()))
            )
        ),

        Assert(
            BytesGe(
                BytesMul(Itob(seller_to_send.get()), Itob(buyer_sell_amount.get())),
                BytesMul(Itob(buyer_to_send.get()), Itob(buyer_buy_amount.get()))
            )
        ),

        # Validate that we are not sending more than allowed
        buyer_sell_remaining.set(buy_order_onchain.sell_remaining),
        Assert(buyer_sell_remaining.get() >= buyer_to_send.get()),
        seller_sell_remaining.set(sell_order_onchain.sell_remaining),
        Assert(seller_sell_remaining.get() >= seller_to_send.get()),

        # Validate that we are not borrowing more thn allowed
        buyer_borrow_remaining.set(buy_order_onchain.borrow_remaining),
        buyer_to_borrow.set(server_args.buyer_to_borrow),
        Assert(buyer_borrow_remaining.get() >= buyer_to_borrow.get()),

        seller_borrow_remaining.set(sell_order_onchain.borrow_remaining),
        seller_to_borrow.set(server_args.seller_to_borrow),
        Assert(seller_borrow_remaining.get() >= seller_to_borrow.get()),

        # Validate that we are not repaying more than allowed
        buyer_repay_remaining.set(buy_order_onchain.repay_remaining),
        buyer_to_repay.set(server_args.buyer_to_repay),
        Assert(buyer_repay_remaining.get() >= buyer_to_repay.get()),

        seller_repay_remaining.set(sell_order_onchain.repay_remaining),
        seller_to_repay.set(server_args.seller_to_repay),
        Assert(seller_repay_remaining.get() >= seller_to_repay.get()),

        # Validate that the fees are lower than the maximum possible
        buyer_fees.set(server_args.buyer_fees),
        seller_fees.set(server_args.seller_fees),
        Assert(buyer_fees.get() <= (buyer_to_send.get() / MAX_FEES_DIVISOR)),
        Assert(seller_fees.get() <= (buyer_to_send.get() / MAX_FEES_DIVISOR)),

        # We shouldn't borrow / repay more than the assets traded, including fees.
        Assert(buyer_to_borrow.get() <= buyer_to_send.get() + buyer_fees.get()),
        Assert(buyer_to_repay.get() <= seller_to_send.get()),
        Assert(seller_to_borrow.get() <= seller_to_send.get()),
        Assert(seller_to_repay.get() <= buyer_to_send.get() - seller_fees.get()),

        # Generate the updated order book for the buy order
        buyer_new_sell_remaining.set(buyer_sell_remaining.get() - buyer_to_send.get()),
        buyer_new_borrow_remaining.set(buyer_borrow_remaining.get() - buyer_to_borrow.get()),
        buyer_new_repay_remaining.set(buyer_repay_remaining.get() - buyer_to_repay.get()),
        buyer_new_order_onchain.set(buyer_new_sell_remaining, buyer_new_borrow_remaining, buyer_new_repay_remaining),

        # Generate the updated order book for the sell order
        seller_new_sell_remaining.set(seller_sell_remaining.get() - seller_to_send.get()),
        seller_new_borrow_remaining.set(seller_borrow_remaining.get() - seller_to_borrow.get()),
        seller_new_repay_remaining.set(seller_repay_remaining.get() - seller_to_repay.get()),
        seller_new_order_onchain.set(seller_new_sell_remaining, seller_new_borrow_remaining, seller_new_repay_remaining),

        # Calculate the swap amounts
        buyer_buy_delta.set(seller_to_send.get()),
        seller_buy_delta.set(buyer_to_send.get() - seller_fees.get()),
        buyer_sell_delta.set(signed_neg(buyer_to_send.get() + buyer_fees.get())),
        seller_sell_delta.set(signed_neg(seller_to_send.get())),

        # Update the on chain order data
        OrderStateHandler.set_order_onchain(buy_order_id, buyer_new_order_onchain),
        OrderStateHandler.set_order_onchain(sell_order_id, seller_new_order_onchain),

        # Get old health for both users if needed
        buyer_negative_margin.set(server_args.buyer_negative_margin),
        seller_negative_margin.set(server_args.seller_negative_margin),

        If(buyer_negative_margin.get()).Then(
            buyer_old_health.set(cast(abi.ReturnedValue, health_check(buy_account, abi_false))),
        ),

        If(seller_negative_margin.get()).Then(
            seller_old_health.set(cast(abi.ReturnedValue, health_check(sell_account, abi_false))),
        ),

        # Handle borrow updates
        If(buyer_to_borrow.get() > Int(0)).Then(
            neg_borrow.set(signed_neg(buyer_to_borrow.get())),
            cast(Expr, perform_pool_move(buy_account, buyer_sell_instrument, neg_borrow)),
        ),
        If(seller_to_borrow.get() > Int(0)).Then(
            neg_borrow.set(signed_neg(seller_to_borrow.get())),
            cast(Expr, perform_pool_move(sell_account, seller_sell_instrument, neg_borrow)),
        ),

        # Perform swap updates
        cast(Expr, signed_add_to_cash(buy_account, buyer_buy_instrument, buyer_buy_delta)),
        cast(Expr, signed_add_to_cash(sell_account, seller_buy_instrument, seller_buy_delta)),
        cast(Expr, signed_add_to_cash(buy_account, buyer_sell_instrument, buyer_sell_delta)),
        cast(Expr, signed_add_to_cash(sell_account, seller_sell_instrument, seller_sell_delta)),

        # Collect the fees
        cast(Expr, collect_fees(buyer_sell_instrument, buyer_fees)),
        cast(Expr, collect_fees(seller_buy_instrument, seller_fees)),

        # Handle repay updates
        If(buyer_to_repay.get() > Int(0)).Then(
            cast(Expr, perform_pool_move(buy_account, buyer_buy_instrument, buyer_to_repay)),
        ),
        If(seller_to_repay.get() > Int(0)).Then(
            cast(Expr, perform_pool_move(sell_account, seller_buy_instrument, seller_to_repay)),
        ),

        # Validate the users are still healthy
        buyer_health.set(cast(abi.ReturnedValue, health_check(buy_account, abi_false))),
        Assert(Or(Not(signed_ltz(buyer_health.get())), And(buyer_negative_margin.get(), signed_gte(buyer_health.get(), buyer_old_health.get())))),
        seller_health.set(cast(abi.ReturnedValue, health_check(sell_account, abi_false))),
        Assert(Or(Not(signed_ltz(seller_health.get())), And(seller_negative_margin.get(), signed_gte(seller_health.get(), seller_old_health.get())))),
    )
