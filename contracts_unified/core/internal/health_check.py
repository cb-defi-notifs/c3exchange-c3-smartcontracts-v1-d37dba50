"""Calculates the user's health"""
from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    Concat,
    Expr,
    For,
    If,
    Int,
    Itob,
    Log,
    Not,
    Seq,
    WideRatio,
    abi,
)

from contracts_unified.core.internal.perform_pool_move import (
    calculate_accrued_borrow,
    calculate_accrued_lend,
)
from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.core.state_handler.local_handler import LocalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    ExcessMargin,
    InstrumentId,
    InstrumentListElement,
    Price,
    Ratio,
    SignedAmount,
    UserInstrumentData,
)
from contracts_unified.library.constants import PRICECASTER_RESCALE_FACTOR, RATIO_ONE
from contracts_unified.library.pricecaster import get_normalized_price
from contracts_unified.library.signed_math import (
    signed_add,
    signed_ltz,
    signed_neg,
    signed_sub,
)


@ABIReturnSubroutine
def health_check(
    account: AccountAddress,
    use_maint: abi.Bool,
    *,
    output: ExcessMargin,
) -> Expr:
    """Calculates the user's health"""

    count = abi.Uint64()

    user_data = UserInstrumentData()
    cash = Amount()
    principal = SignedAmount()
    index = abi.Uint64()

    instrument_id = InstrumentId()
    instrument = InstrumentListElement()
    loaned_balance = SignedAmount()
    balance_sum = SignedAmount()
    has_lend = abi.Uint64()

    haircut = Ratio()
    margin = Ratio()

    optimal_utilization = Ratio()

    price = Price()

    return Seq(
        # Clear output
        output.set(Int(0)),

        # Loop over instruments
        count.set(cast(abi.ReturnedValue, LocalStateHandler.get_user_instrument_count(account))),
        For(
            instrument_id.set(Int(0)),
            instrument_id.get() < count.get(),
            instrument_id.set(instrument_id.get() + Int(1)),
        ).Do(
            Seq(
                # Extract user position
                user_data.set(cast(abi.ReturnedValue, LocalStateHandler.get_position(account, instrument_id))),
                cash.set(user_data.cash),
                principal.set(user_data.principal),
                index.set(user_data.index),

                If(cash.get() | principal.get()).Then(
                    # Get price
                    price.set(cast(abi.ReturnedValue, get_normalized_price(instrument_id))),

                    # Get instrument
                    instrument.set(cast(abi.ReturnedValue, GlobalStateHandler.get_instrument(instrument_id))),

                    # Get loan balance(netting)
                    If(principal.get() != Int(0))
                    .Then(
                        has_lend.set(Not(signed_ltz(principal.get()))),
                        If(has_lend.get())
                        .Then(
                            instrument.lend_index.use(lambda lend_index:
                                loaned_balance.set(calculate_accrued_lend(principal, index, lend_index))
                            )
                        )
                        .Else(
                            instrument.borrow_index.use(lambda borrow_index:
                                loaned_balance.set(calculate_accrued_borrow(principal, index, borrow_index)),
                            )
                        ),
                    )
                    .Else(
                        has_lend.set(Int(0)),
                        loaned_balance.set(Int(0))
                    ),

                    # Calculate balance sum
                    balance_sum.set(signed_add(cash.get(), loaned_balance.get())),

                    # Get risk factors
                    # Load risk factors
                    If(use_maint.get())
                    .Then(
                        instrument.maintenance_haircut.store_into(haircut),
                        instrument.maintenance_margin.store_into(margin),
                    )
                    .Else(
                        instrument.initial_haircut.store_into(haircut),
                        instrument.initial_margin.store_into(margin),
                    ),

                    # Load optimal utilization
                    instrument.optimal_utilization.store_into(optimal_utilization),

                    # Calculate health for this asset and add to output
                    # Add first term, health += price * sum * ratio
                    If(signed_ltz(balance_sum.get()))
                    .Then(
                        output.set(signed_sub(output.get(), WideRatio([price.get(), signed_neg(balance_sum.get()), Int(RATIO_ONE) + margin.get()], [Int(PRICECASTER_RESCALE_FACTOR * RATIO_ONE)])))
                    )
                    .Else(
                        output.set(signed_add(output.get(), WideRatio([price.get(), balance_sum.get(), Int(RATIO_ONE) - haircut.get()], [Int(PRICECASTER_RESCALE_FACTOR * RATIO_ONE)])))
                    ),

                    # Lend positions should be further multiplied by (1 - optimal_utilization)
                    # We already included the 1 term, so we need to subtract the optimal utilization
                    If(has_lend.get())
                    .Then(
                        output.set(
                            signed_sub(
                                output.get(),
                                WideRatio(
                                    [price.get(), loaned_balance.get(), Int(RATIO_ONE) - haircut.get(), optimal_utilization.get()],
                                    # Normalize haircut and utilization
                                    [Int(PRICECASTER_RESCALE_FACTOR * RATIO_ONE * RATIO_ONE)],
                                ),
                            )
                        )
                    )
                ),
            )
        ),
        Log(Concat(account.get(), Itob(output.get())))
    )
