"""Moves funds between two accounts"""


from typing import cast

from pyteal import ABIReturnSubroutine, Assert, Expr, For, Int, Not, Seq, abi

from contracts_unified.core.internal.health_check import health_check
from contracts_unified.core.internal.liquidation_calculator import closer_to_zero
from contracts_unified.core.internal.move import signed_account_move_baskets
from contracts_unified.core.internal.perform_pool_move import perform_pool_move
from contracts_unified.core.internal.setup import setup
from contracts_unified.core.internal.validate_sender import sender_is_sig_validator
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    ExcessMargin,
    SignedInstrumentBasket,
)
from contracts_unified.library.c3types_user import (
    AccountMoveData,
    DelegationChain,
    OperationId,
    OperationMetaData,
)
from contracts_unified.library.signed_math import signed_ltz


@ABIReturnSubroutine
def account_move(
    source_account: AccountAddress,
    user_op: OperationMetaData,
    delegation_chain: DelegationChain,
    _server_data: abi.DynamicBytes,
    opup_budget: Amount,
) -> Expr:
    """Moves funds between two accounts

    Arguments:

    source_account (AccountAddress): Source account address.
    user_op (OperationMetaData): Operation metadata containing destination account, cash and pool.
    _delegation_chain (DelegationChain): Delegation chain.  Unused.
    _server_data (abi.DynamicBytes): Server data.  Unused.
    opup_budget (Amount): Additional computation budget to allocate to this transaction.

    """

    # Constants
    abi_false = abi.Bool()

    # Extracted operation data
    data = AccountMoveData()
    cash = abi.make(SignedInstrumentBasket)
    pool = abi.make(SignedInstrumentBasket)

    # Sender and receiver accounts
    destination_account = AccountAddress()

    # Health check
    health = ExcessMargin()

    i = abi.Uint64()
    length = abi.Uint64()
    abi_zero_int = abi.Uint64()

    return Seq(
        setup(opup_budget.get()),

        # Set constants
        abi_false.set(Int(0)),
        abi_zero_int.set(Int(0)),

        # Validate sender
        cast(Expr, sender_is_sig_validator()),

        # No delegation is allowed for account move
        Assert(delegation_chain.length() == Int(0)),

        # Get the source and destination accounts
        user_op.operation.use(lambda op_data:
            Seq(
                data.decode(op_data.get()),
                data.operation.use(lambda op: Assert(op.get() == OperationId.AccountMove)),
                data.destination_account.store_into(destination_account),
                data.cash.store_into(cash),
                data.pool.store_into(pool),
            )
        ),

        # Validate the source account is not the destination account
        Assert(source_account.get() != destination_account.get()),

        # Check the closer-to-zero condition for the pool basket
        cast(Expr, closer_to_zero(source_account, pool)),

        # Update both users to the current index
        length.set(pool.length()),
        For(i.set(Int(0)), i.get() < length.get(), i.set(i.get() + Int(1))).Do(
            pool[i.get()].use(lambda instrument_amount:
                instrument_amount.instrument.use(lambda instrument:
                    Seq(
                        cast(Expr, perform_pool_move(source_account, instrument, abi_zero_int)),
                        cast(Expr, perform_pool_move(destination_account, instrument, abi_zero_int))
                    )
                )
            )
        ),

        # Perform update
        cast(Expr, signed_account_move_baskets(source_account, destination_account, cash, pool, abi_false, abi_false)),

        # Check health
        # NOTE: No need to check old vs new because all account moves make health worse
        health.set(health_check(source_account, abi_false)),
        Assert(Not(signed_ltz(health.get()))),
    )
