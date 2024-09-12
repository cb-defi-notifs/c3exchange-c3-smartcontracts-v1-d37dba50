"""
Implements Core contract deposit ABI method.
"""


from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    And,
    Assert,
    Bytes,
    Cond,
    Expr,
    Global,
    If,
    Int,
    Not,
    Or,
    Seq,
    TxnType,
    abi,
)

from contracts_unified.core.internal.move import signed_add_to_cash
from contracts_unified.core.internal.perform_pool_move import perform_pool_move
from contracts_unified.core.internal.setup import setup
from contracts_unified.core.internal.validate_sender import sender_is_sig_validator
from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    DepositWord,
    InstrumentId,
    InstrumentListElement,
)
from contracts_unified.library.signed_math import signed_ltz


@ABIReturnSubroutine
def inner_deposit_asset(
    account: AccountAddress,
    payload: DepositWord,
    instrument_id: InstrumentId,
    amount: Amount,
    instant_pool_move: Amount,
) -> Expr:
    """Deposits assets to a given user. Instant pool move is used to then move deposited funds to the pool if requested."""

    return Seq(
        # Validate sender is a user proxy
        cast(Expr, sender_is_sig_validator()),

        # Validate payload keyword
        Assert(payload.get() == Bytes("deposit")),

        # Validate deposit amount is positive
        Assert(Not(Or(signed_ltz(amount.get()), signed_ltz(instant_pool_move.get())))),

        # Update asset balance
        cast(Expr, signed_add_to_cash(account, instrument_id, amount)),

        # Perform instant pool move
        If(instant_pool_move.get() != Int(0))
        .Then(
            cast(Expr, perform_pool_move(account, instrument_id, instant_pool_move))
        ),
    )

@ABIReturnSubroutine
def deposit(
    account: AccountAddress,
    deposit_txn: abi.Transaction,
    payload: DepositWord,
    instrument_id: InstrumentId,
    instant_pool_move: Amount,
    opup_budget: Amount,
) -> Expr:
    """Implements the standard Deposit contract method.

    Arguments:

    account (AccountAddress): Target account address to deposit to.
    deposit_txn (Transaction): The ABI "Transaction-Type" argument referencing the previous transaction to this call in the "Standard Deposit" group.  Must be of type "payment" of "asset transfer".
    payload (DepositWord): Payload, must equal to "Deposit" string-literal.
    instrument_id (InstrumentId): Instrument to transfer.
    instant_pool_move (Amount): Optional amount to move to instant pool.
    opup_budget (Amount): Additional computation budget to allocate to this transaction.

"""

    deposit_asset_id = abi.Uint64()
    deposit_amount = abi.Uint64()
    element = InstrumentListElement()

    return Seq(
        # Generate budget for deposit
        setup(opup_budget.get()),

        # Validate deposit transaction
        Assert(
            And(
                # We don't really need to check rekey_to field,
                # but it's still good for us if we don't have to support unintended use cases.
                deposit_txn.get().rekey_to() == Global.zero_address(),
                deposit_txn.get().asset_close_to() == Global.zero_address(),
            )
        ),

        # Get deposit info from transaction
        Cond(
            [deposit_txn.get().type_enum() == TxnType.AssetTransfer, Seq(
                Assert(deposit_txn.get().asset_receiver() == Global.current_application_address()),
                deposit_asset_id.set(deposit_txn.get().xfer_asset()),
                deposit_amount.set(deposit_txn.get().asset_amount()),
            )],
            [deposit_txn.get().type_enum() == TxnType.Payment, Seq(
                Assert(deposit_txn.get().receiver() == Global.current_application_address()),
                deposit_asset_id.set(Int(0)),
                deposit_amount.set(deposit_txn.get().amount()),
            )],
        ),

        # Validate deposit asset is given instrument ID
        element.set(cast(abi.ReturnedValue, GlobalStateHandler.get_instrument(instrument_id))),
        element.asset_id.use(lambda asset_id: Assert(deposit_asset_id.get() == asset_id.get())),

        # Perform deposit
        cast(Expr, inner_deposit_asset(account, payload, instrument_id, deposit_amount, instant_pool_move)),
    )
