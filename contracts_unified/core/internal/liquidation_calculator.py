"""Calculations used during liquidation"""


from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    And,
    Assert,
    Concat,
    Expr,
    Extract,
    For,
    If,
    Int,
    Itob,
    Not,
    Or,
    ScratchVar,
    Seq,
    TealType,
    WideRatio,
    abi,
)

from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.core.state_handler.local_handler import LocalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    InstrumentId,
    InstrumentListElement,
    Price,
    Ratio,
    SignedInstrumentAmount,
    SignedInstrumentBasket,
    UserInstrumentData,
)
from contracts_unified.library.constants import PRICECASTER_RESCALE_FACTOR, RATIO_ONE
from contracts_unified.library.pricecaster import get_normalized_price
from contracts_unified.library.signed_math import (
    signed_abs,
    signed_gte,
    signed_ltz,
    signed_neg,
)


@ABIReturnSubroutine
def calculate_basket_value(
    cash_basket: SignedInstrumentBasket,
    add_negatives: abi.Bool,
    factor: Ratio,  # NOTE: This is ignored if use_bonus is false
    use_bonus: abi.Bool,
    invert_bonus_or_use_margin: abi.Bool,
    use_opt_utilization: abi.Bool,  # NOTE: This is ignored if use_bonus is true
    *,
    output: Price,
) -> Expr:
    """Calculate the value of a basket either using the bonus or hair cut/margin"""

    length = abi.Uint64()
    i = InstrumentId()
    instrument_amount = SignedInstrumentAmount()
    price = Price()
    instrument_data = InstrumentListElement()

    margin_or_haircut = Ratio()
    optimal_utilization = Ratio()
    bonus = abi.Uint64()

    assert RATIO_ONE * RATIO_ONE * PRICECASTER_RESCALE_FACTOR < 2 ** 64

    return Seq(
        # Clear accumulator
        output.set(Int(0)),

        # Iterate assets
        length.set(cash_basket.length()),
        For(i.set(Int(0)), i.get() < length.get(), i.set(i.get() + Int(1))).Do(
            instrument_amount.set(cash_basket[i.get()]),
            instrument_amount.instrument.use(lambda instrument:
                instrument_amount.amount.use(lambda amount:
                    Seq(
                        # Add to accumulator when the sign matches the requested sign
                        # NOTE: Compare with zero needed to ensure sign flag is in the lowest bit
                        If((signed_ltz(amount.get()) != Int(0)) == add_negatives.get())
                        .Then(
                            # Get price of insrument
                            price.set(cast(abi.ReturnedValue, get_normalized_price(instrument))),

                            # Get the instrument data
                            instrument_data.set(cast(abi.ReturnedValue, GlobalStateHandler.get_instrument(instrument))),

                            If(use_bonus.get())
                            .Then(
                                # Get haircut value
                                margin_or_haircut.set(instrument_data.maintenance_haircut),

                                # Calculate bonus
                                # bonus = 1 + factor * haircut
                                bonus.set(Int(RATIO_ONE) + WideRatio([factor.get(), margin_or_haircut.get()], [Int(RATIO_ONE)])),

                                # Accumulate total, rescaling by PRICECASTER_RESCALE_FACTOR to avoid overflow
                                output.set(
                                    output.get() +
                                    If(invert_bonus_or_use_margin.get())
                                    .Then(
                                        # amount * price / bonus = amount * price * (1 / bonus)
                                        WideRatio([signed_abs(amount.get()), price.get(), Int(RATIO_ONE)], [bonus.get(), Int(PRICECASTER_RESCALE_FACTOR)])
                                    )
                                    .Else(
                                        # amount * price * bonus = amount * price * bonus / 1
                                        WideRatio([signed_abs(amount.get()), price.get(), bonus.get()], [Int(RATIO_ONE * PRICECASTER_RESCALE_FACTOR)])
                                    )
                                )
                            )
                            .Else(
                                # Get margin or haircut factor
                                If(invert_bonus_or_use_margin.get())
                                .Then(
                                    instrument_data.initial_margin.use(lambda margin:
                                        margin_or_haircut.set(Int(RATIO_ONE) + margin.get())
                                    )
                                )
                                .Else(
                                    instrument_data.initial_haircut.use(lambda haircut:
                                        margin_or_haircut.set(Int(RATIO_ONE) - haircut.get())
                                    )
                                ),

                                # Get optimal utilization factor
                                If(use_opt_utilization.get())
                                .Then(
                                    instrument_data.optimal_utilization.use(lambda opt_util:
                                        optimal_utilization.set(Int(RATIO_ONE) - opt_util.get())
                                    )
                                )
                                .Else(
                                    optimal_utilization.set(Int(RATIO_ONE))
                                ),

                                # Add instrument's value to the total, respecting margin_or_haircut and optimal utilization if required
                                # value += amount * price / RESCALE * margin_or_haircut / 1 * (optimal_utilization or 1) / 1
                                output.set(
                                    output.get() +
                                    WideRatio([signed_abs(amount.get()), price.get(), margin_or_haircut.get(), optimal_utilization.get()], [Int(RATIO_ONE * RATIO_ONE * PRICECASTER_RESCALE_FACTOR)])
                                ),
                            ),
                        )
                    )
                )
            ),
        ),
    )


@ABIReturnSubroutine
def scale_basket(
    basket: SignedInstrumentBasket,
    numerator: abi.Uint64,
    denominator: abi.Uint64,
    *,
    output: SignedInstrumentBasket,
) -> Expr:
    """
    Scale the value of basket by some wide ratio
    NOTE: Assumes input ratio is positive/positive
    """

    length = abi.Uint64()
    i = InstrumentId()
    result = ScratchVar(TealType.bytes)

    return Seq(
        length.set(basket.length()),
        result.store(Extract(Itob(length.get()), Int(6), Int(2))),
        For(i.set(Int(0)), i.get() < length.get(), i.set(i.get() + Int(1))).Do(
            basket[i.get()].use(lambda instrument_amount:
                instrument_amount.instrument.use(lambda instrument:
                    instrument_amount.amount.use(lambda amount:
                        result.store(
                            Concat(
                                result.load(),
                                Extract(Itob(instrument.get()), Int(7), Int(1)),
                                If(signed_ltz(amount.get())).Then(
                                    Itob(signed_neg(WideRatio([signed_neg(amount.get()), numerator.get()], [denominator.get()])))
                                ).Else(
                                    Itob(WideRatio([amount.get(), numerator.get()], [denominator.get()]))
                                )
                            )
                        )
                    )
                )
            )
        ),

        # Encode result
        output.decode(result.load()),
    )


@ABIReturnSubroutine
def closer_to_zero(
    account: AccountAddress,
    pool_basket: SignedInstrumentBasket,
) -> Expr:
    """
    Ensure that the basket amounts are closer to zero than the liquidatee's pool balance
    This is to prevent the liquidator from being able to give a user who is positive in a given
    pool more of that pool's asset, or take away from a user who is negative in a given pool.

    If you are lending X(positive principal), you will never end up lending more after liquidation. If you are borrowing
    X, you will never end up borrowing more after liquidation.
    """

    length = abi.Uint64()
    i = InstrumentId()
    pool_data = UserInstrumentData()
    instrument_id = InstrumentId()
    user_pool_balance = Amount()
    basket_amount = Amount()

    return Seq(
        length.set(pool_basket.length()),
        For(i.set(Int(0)), i.get() < length.get(), i.set(i.get() + Int(1))).Do(
            pool_basket[i.get()].use(lambda entry:
                Seq(
                    instrument_id.set(entry.instrument),
                    basket_amount.set(entry.amount),
                    pool_data.set(cast(abi.ReturnedValue, LocalStateHandler.get_position(account, instrument_id))),
                    user_pool_balance.set(pool_data.principal),
                    If(signed_ltz(user_pool_balance.get()))
                    .Then(
                        # User owes money to the pool, thus liquidation must increase the pool's balance
                        Assert(And(Or(signed_ltz(basket_amount.get()), basket_amount.get() == Int(0)), signed_gte(basket_amount.get(), user_pool_balance.get()))),
                    )
                    .Else(
                        # User has money in the pool, thus liquidation must decrease the pool's balance
                        Assert(And(Not(signed_ltz(basket_amount.get())), signed_gte(user_pool_balance.get(), basket_amount.get()))),
                    )
                )
            )
        )
    )
