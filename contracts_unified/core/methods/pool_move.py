"""
Implements Core contract method for transferring user's instruments to/from a pool.
"""


from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    Assert,
    Expr,
    If,
    Int,
    Not,
    Or,
    Seq,
    WideRatio,
    abi,
)

from contracts_unified.core.internal.health_check import health_check
from contracts_unified.core.internal.move import signed_add_to_cash
from contracts_unified.core.internal.perform_pool_move import perform_pool_move
from contracts_unified.core.internal.setup import setup
from contracts_unified.core.internal.validate_sender import sender_is_sig_validator
from contracts_unified.core.state_handler.local_handler import LocalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    ExcessMargin,
    InstrumentId,
    Price,
    SignedAmount,
    UserInstrumentData,
)
from contracts_unified.library.c3types_user import (
    DelegationChain,
    OperationId,
    OperationMetaData,
    PoolMoveData,
)
from contracts_unified.library.constants import PRICECASTER_RESCALE_FACTOR
from contracts_unified.library.pricecaster import get_normalized_price
from contracts_unified.library.signed_math import (
    signed_add,
    signed_gte,
    signed_ltz,
    signed_neg,
)


@ABIReturnSubroutine
def pool_move(
    account: AccountAddress,
    user_op: OperationMetaData,
    _delegation_chain: DelegationChain,
    _server_data: abi.DynamicBytes,
    opup_budget: Amount,
) -> Expr:
    """Transfers instruments from user's address to the pool

    Arguments:

    account (AccountAddress): User's account address.
    user_op (OperationMetaData): Operation metadata containing a basket of instruments.
    _delegation_chain (DelegationChain): Delegation chain.  Unused.
    _server_data (abi.DynamicBytes): Server data.  Unused.
    opup_budget (Amount): Additional computation budget to allocate to this transaction.

    """

    abi_false = abi.Bool()

    user_old_health = ExcessMargin()
    user_health = ExcessMargin()

    data = PoolMoveData()
    instrument = InstrumentId()
    amount = SignedAmount()

    user_data = UserInstrumentData()
    price = Price()
    cash = Amount()
    neg_cash = SignedAmount()

    return Seq(
        setup(opup_budget.get()),

        # Load constants
        abi_false.set(Int(0)),

        # Validate sender is a user proxy
        cast(Expr, sender_is_sig_validator()),

        # Get basket from user_op.data
        user_op.operation.use(lambda op_data:
            Seq(
                data.decode(op_data.get()),
                data.operation.use(lambda op: Assert(op.get() == OperationId.PoolMove)),
                instrument.set(data.instrument),
                amount.set(data.amount),
            )
        ),

        # Get old health
        user_old_health.set(cast(abi.ReturnedValue, health_check(account, abi_false))),

        # Move funds
        cast(Expr, perform_pool_move(account, instrument, amount)),

        # When there is a negative movement, we need to check that the user can support itself without netting
        If(signed_ltz(amount.get())).Then(
            # Get instrument price
            price.set(cast(abi.ReturnedValue, get_normalized_price(instrument))),
            # Extract user cash
            user_data.set(cast(abi.ReturnedValue, LocalStateHandler.get_position(account, instrument))),
            cash.set(user_data.cash),
            neg_cash.set(signed_neg(cash.get())),
            # Remove all user cash temporarily
            cast(Expr, signed_add_to_cash(account, instrument, neg_cash)),
            # Recalculate health without netting the borrowed asset, ensure it is positive
            user_health.set(cast(abi.ReturnedValue, health_check(account, abi_false))),
            user_health.set(signed_add(user_health.get(), WideRatio([price.get(), cash.get()], [Int(PRICECASTER_RESCALE_FACTOR)]))),
            Assert(Not(signed_ltz(user_health.get()))),
            # Add all the cash back
            cast(Expr, signed_add_to_cash(account, instrument, cash)),
        ),

        # Validate user is still healthy
        user_health.set(cast(abi.ReturnedValue, health_check(account, abi_false))),
        Assert(Or(Not(signed_ltz(user_health.get())), signed_gte(user_health.get(), user_old_health.get()))),
    )
