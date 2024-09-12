"""Utility functions to move assets between and within accounts"""


from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    And,
    Assert,
    Expr,
    For,
    If,
    Int,
    Not,
    Reject,
    Seq,
    abi,
)

from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.core.state_handler.local_handler import LocalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    InstrumentId,
    SignedAmount,
    SignedInstrumentBasket,
    UserInstrumentData,
)
from contracts_unified.library.signed_math import signed_add, signed_ltz, signed_neg


@ABIReturnSubroutine
def signed_add_to_cash(
    account: AccountAddress,
    instrument_id: InstrumentId,
    amount: Amount,
) -> Expr:
    """Adds amount to the user's asset balance"""

    data = UserInstrumentData()
    new_cash = SignedAmount()

    return Seq(
        # Load user data
        data.set(cast(abi.ReturnedValue, LocalStateHandler.get_position(account, instrument_id))),

        # Update user data
        data.cash.use(lambda cash:
            new_cash.set(signed_add(amount.get(), cash.get())),
        ),

        # Validate the result is positive
        Assert(Not(signed_ltz(new_cash.get()))),

        # Update data
        data.principal.use(lambda principal:
            data.index.use(lambda index:
                data.set(
                    new_cash,
                    principal,
                    index,
                )
            )
        ),

        cast(Expr, LocalStateHandler.set_position(account, instrument_id, data)),
    )

@ABIReturnSubroutine
def signed_add_to_pool(
    account: AccountAddress,
    instrument_id: InstrumentId,
    amount: SignedAmount,
) -> Expr:
    """Adds amount to the user's pool balance"""

    data = UserInstrumentData()
    new_principal = SignedAmount()

    return Seq(
        # Load user data
        data.set(cast(abi.ReturnedValue, LocalStateHandler.get_position(account, instrument_id))),

        # Update user data
        data.principal.use(lambda principal:
            new_principal.set(signed_add(amount.get(), principal.get())),
        ),

        # Update data
        data.cash.use(lambda cash:
            data.index.use(lambda index:
                data.set(
                    cash,
                    new_principal,
                    index,
                )
            )
        ),

        cast(Expr, LocalStateHandler.set_position(account, instrument_id, data)),
    )

# NOTE: Not a subroutine for performance reasons
def account_move_single_cash(
    source_account: AccountAddress,
    destination_account: AccountAddress,
    instrument_id: InstrumentId,
    amount: Amount,
    allow_negative: abi.Bool,
) -> Expr:
    """Moves amount of a single asset between two accounts"""

    inv_amount = SignedAmount()

    return Seq(
        # Validate the amount is positive if required
        If(And(Not(allow_negative.get()), signed_ltz(amount.get())), Reject()),

        # Calculate inverse amount
        inv_amount.set(signed_neg(amount.get())),

        # Decrement source account
        cast(Expr, signed_add_to_cash(source_account, instrument_id, inv_amount)),

        # Increment destination account
        cast(Expr, signed_add_to_cash(destination_account, instrument_id, amount)),
    )


# NOTE: Not a subroutine for performance reasons
def account_move_single_pool(
    source_account: AccountAddress,
    destination_account: AccountAddress,
    instrument_id: InstrumentId,
    amount: Amount,
    allow_negative: abi.Bool,
) -> Expr:
    """Moves amount of an amount from a single pool between two accounts"""

    inv_amount = SignedAmount()

    return Seq(
        # Validate the amount is positive if required
        If(And(Not(allow_negative.get()), signed_ltz(amount.get())), Reject()),

        # Calulate inverse amount
        inv_amount.set(signed_neg(amount.get())),

        # Decrement source account
        cast(Expr, signed_add_to_pool(source_account, instrument_id, inv_amount)),

        # Increment destination account
        cast(Expr, signed_add_to_pool(destination_account, instrument_id, amount)),
    )

@ABIReturnSubroutine
def signed_account_move_baskets(
    source_account: AccountAddress,
    destination_account: AccountAddress,
    cash_basket: SignedInstrumentBasket,
    pool_basket: SignedInstrumentBasket,
    allow_negative_assets: abi.Bool,
    allow_negative_liabilities: abi.Bool,
) -> Expr:
    """Moves funds between two accounts"""

    i = abi.Uint64()
    length = abi.Uint64()

    return Seq(
        # Iterate the asset basket
        length.set(cash_basket.length()),
        For(i.set(Int(0)), i.get() < length.get(), i.set(i.get() + Int(1))).Do(
            cash_basket[i.get()].use(lambda instrument_amount:
                instrument_amount.instrument.use(lambda instrument:
                    instrument_amount.amount.use(lambda amount:
                        cast(Expr, account_move_single_cash(source_account, destination_account, instrument, amount, allow_negative_assets))
                    )
                )
            )
        ),

        # Iterate the pool basket
        length.set(pool_basket.length()),
        For(i.set(Int(0)), i.get() < length.get(), i.set(i.get() + Int(1))).Do(
            pool_basket[i.get()].use(lambda instrument_amount:
                instrument_amount.instrument.use(lambda instrument:
                    instrument_amount.amount.use(lambda amount:
                        cast(Expr, account_move_single_pool(source_account, destination_account, instrument, amount, allow_negative_liabilities))
                    )
                )
            )
        ),
    )

@ABIReturnSubroutine
def collect_fees(
    instrument_id: InstrumentId,
    amount: Amount,
) -> Expr:
    """Adds amount to the fees target balance"""

    fee_target_account = AccountAddress()

    return Seq(
        fee_target_account.set(GlobalStateHandler.get_fee_target()),
        cast(Expr, signed_add_to_cash(fee_target_account, instrument_id, amount))
    )
