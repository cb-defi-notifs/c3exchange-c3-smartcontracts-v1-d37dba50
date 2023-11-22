"""Update the pool data for a given instrument and loan amount"""
from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    Assert,
    Expr,
    Global,
    If,
    Int,
    Not,
    Seq,
    WideRatio,
    abi,
)

from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.core.state_handler.local_handler import LocalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    AssetId,
    InstrumentId,
    InstrumentListElement,
    InterestRate,
    Ratio,
    RelativeTimestamp,
    SignedAmount,
    Timestamp,
    UserInstrumentData,
)
from contracts_unified.library.constants import RATE_ONE, RATIO_ONE
from contracts_unified.library.math import teal_expt
from contracts_unified.library.signed_math import (
    signed_add,
    signed_ltz,
    signed_max,
    signed_min,
    signed_neg,
    signed_sub,
)


# NOTE: Not a subroutine for performance reasons
def calculate_accrued_borrow(
    user_principal: SignedAmount,
    user_index: InterestRate,
    pool_borrow_index: InterestRate,
) -> Expr:
    """Calculate the accrued borrow with user instrument data"""
    # BB_t(u) = PB(u) * BI_t / BI_{t(u)}
    borrowed = SignedAmount()
    result = SignedAmount()
    return Seq(
        borrowed.set(signed_neg(user_principal.get())),
        result.set(WideRatio([borrowed.get(), pool_borrow_index.get()], [user_index.get()])),
        signed_neg(result.get() + (result.get() == borrowed.get())),
    )


# NOTE: Not a subroutine for performance reasons
def calculate_accrued_lend(
    user_principal: SignedAmount,
    user_index: InterestRate,
    pool_lend_index: InterestRate,
) -> Expr:
    """Calculate the accrued lend with user instrument data"""
    # LB_t(u) = PL(u) * LI_t / LI_{t(u)}
    return WideRatio([user_principal.get(), pool_lend_index.get()], [user_index.get()])


@ABIReturnSubroutine
def perform_pool_move(
    account: AccountAddress,
    instrument_id: InstrumentId,
    transfer_amount: SignedAmount,
) -> Expr:
    """
    Transfers from the user to the pool `transfer_amount`.
    The function takes the following steps:
      1. Calculates global accrued interest
      2. Capitalizes the users balance by updating the
         user's principal with the user's accrued interest
      3. Transfer between the user and the pool

    Parameters
    ----------
    user_position: current pool position of the user on `instrument_id`
    instrument_id: instrument index
    transfer_amount: amount to be transfered from the user to the pool.
        a positive value indicates that the user is sending to the pool (repaying and/or subscribing)
        a negative value indicates that the user is receiving from the pool (borrowing and/or redeeming)
    output: the user's position on the pool after the transfer
    """

    # Instrument's attributes that change as part of this operation
    new_pool_last_update_time = RelativeTimestamp()
    old_pool_last_update_time = RelativeTimestamp()

    new_pool_borrowed = Amount()
    old_pool_borrowed = Amount()

    new_pool_liquidity = Amount()
    old_pool_liquidity = Amount()

    new_pool_borrow_index = InterestRate()
    old_pool_borrow_index = InterestRate()

    new_pool_lend_index = InterestRate()
    old_pool_lend_index = InterestRate()

    # Instrument attributes that are not affected by this operation
    asset_id = AssetId()
    initial_haircut = Ratio()
    initial_margin = Ratio()
    maintenance_haircut = Ratio()
    maintenance_margin = Ratio()

    optimal_utilization_ratio = Ratio()
    optimal_utilization_rate = InterestRate()
    min_rate = InterestRate()
    opt_rate = InterestRate()
    max_rate = InterestRate()

    # User's attributes
    user_position = UserInstrumentData()
    new_user_principal = SignedAmount()
    old_user_principal = SignedAmount()
    new_user_index = InterestRate()
    old_user_index = InterestRate()
    new_user_cash = Amount()
    old_user_cash = Amount()

    # Variables for intermediate calculations
    old_utilization_rate = InterestRate()
    old_interest_rate = InterestRate()
    delta_time = Timestamp()
    compounding_per_second_rate = InterestRate()
    compounding_per_period_rate = InterestRate()

    pool_accrued_interest = Amount()

    liquidity_transfer = SignedAmount()
    borrowed_transfer = SignedAmount()

    remainder = SignedAmount()

    instrument_state = InstrumentListElement()
    new_instrument_state = InstrumentListElement()

    return Seq(
        # Loads current instrument state
        instrument_state.set(cast(abi.ReturnedValue, GlobalStateHandler.get_instrument(instrument_id))),

        instrument_state.asset_id.store_into(asset_id),
        # Loads pool data
        instrument_state.last_update_time.store_into(old_pool_last_update_time),
        instrument_state.borrowed.store_into(old_pool_borrowed),
        instrument_state.liquidity.store_into(old_pool_liquidity),
        instrument_state.borrow_index.store_into(old_pool_borrow_index),
        instrument_state.lend_index.store_into(old_pool_lend_index),

        # Loads interest curve data
        instrument_state.optimal_utilization.store_into(optimal_utilization_ratio),
        optimal_utilization_rate.set(WideRatio([optimal_utilization_ratio.get(), Int(RATE_ONE)], [Int(RATIO_ONE)])),
        instrument_state.min_rate.store_into(min_rate),
        instrument_state.opt_rate.store_into(opt_rate),
        instrument_state.max_rate.store_into(max_rate),

        # Loads haircuts and margins
        instrument_state.initial_haircut.store_into(initial_haircut),
        instrument_state.initial_margin.store_into(initial_margin),
        instrument_state.maintenance_haircut.store_into(maintenance_haircut),
        instrument_state.maintenance_margin.store_into(maintenance_margin),

        # Calculates the new timestamp
        # NOTE: Updates to this can be controlled via the algosdk function setBlockOffsetTimestamp
        new_pool_last_update_time.set(GlobalStateHandler.get_relative_timestamp()),

        ###############################################################################################################
        # 1.
        # Calculates the accrued interest in the pool since the last update
        # and reflects that on the total liquidity and borrow amount.

        # 1.1
        # AI_t = ((BI_t / BI_{t-1})-1) * B_{t-1} = ((1+R_{t_1})^dT - 1) * B_{t-1}

        # 1.1.1
        # Calculates the pool's utilization
        # U_{t-1} = B_{t-1} / L_{t-1} = B_{t-1} * 1 / L_{t-1}
        old_utilization_rate.set(
            If(old_pool_liquidity.get() == Int(0))
            .Then(Int(0))
            .Else(WideRatio([old_pool_borrowed.get(), Int(RATE_ONE)], [old_pool_liquidity.get()]))
        ),

        # 1.1.2
        # Calculates interest rate per second for the period since the last update
        # R_{t-1} = R_min + U_{t-1} / U_opt * R_slope1 if U_{t-1} < U_opt
        # R_{t-1} = R_opt + (U_{t-1}-U_opt) / (1 - U_opt) * R_slope2 if U_{t-1} >= U_opt
        old_interest_rate.set(
            If(old_utilization_rate.get() < optimal_utilization_rate.get())
            .Then(
                min_rate.get()
                + WideRatio(
                    [old_utilization_rate.get(), opt_rate.get() - min_rate.get()],
                    [optimal_utilization_rate.get()]
                )
            )
            .Else(
                opt_rate.get()
                + WideRatio(
                    [old_utilization_rate.get() - optimal_utilization_rate.get(), max_rate.get() - opt_rate.get()],
                    [Int(RATE_ONE) - optimal_utilization_rate.get()]
                )
            )
        ),

        # 1.1.3
        # Calculates time since previous update
        delta_time.set(new_pool_last_update_time.get() - old_pool_last_update_time.get()),

        # 1.1.4
        # AI_t = ((BI_t / BI_{t-1})-1) * B_{t-1} = ((1+R_{t_1})^dT - 1) * B_{t-1}
        compounding_per_second_rate.set(Int(RATE_ONE) + old_interest_rate.get()),
        compounding_per_period_rate.set(teal_expt(compounding_per_second_rate, delta_time)),
        pool_accrued_interest.set(
            WideRatio(
                [compounding_per_period_rate.get() - Int(RATE_ONE), old_pool_borrowed.get()],
                [Int(RATE_ONE)],
            )
        ),

        # 1.2
        # Capitalize pool accrued interest into liquidity and borrowed amounts
        new_pool_borrowed.set(old_pool_borrowed.get() + pool_accrued_interest.get()),
        new_pool_liquidity.set(old_pool_liquidity.get() + pool_accrued_interest.get()),

        # 1.3
        # Updates pool indexes
        new_pool_borrow_index.set(
            If(old_pool_borrowed.get() == Int(0))
            .Then(
                Int(RATE_ONE)
            )
            .Else(
                WideRatio([old_pool_borrow_index.get(), new_pool_borrowed.get()], [old_pool_borrowed.get()])
            )
        ),
        new_pool_lend_index.set(
            If(old_pool_liquidity.get() == Int(0))
            .Then(
                Int(RATE_ONE)
            )
            .Else(
                WideRatio([old_pool_lend_index.get(), new_pool_liquidity.get()], [old_pool_liquidity.get()])
            )
        ),

        # We only perform the pool move if a user was given, otherwise we just update the global instrument data
        If(account.get() != Global.zero_address()).Then(
            ###############################################################################################################
            # 2
            # Get user data
            user_position.set(cast(abi.ReturnedValue, LocalStateHandler.get_position(account, instrument_id))),
            user_position.cash.store_into(old_user_cash),
            user_position.principal.store_into(old_user_principal),
            user_position.index.store_into(old_user_index),

            # Capitalize user's accrued interest into user's principal
            new_user_principal.set(
                If(old_user_index.get() == Int(0))
                .Then(
                    Int(0)
                )
                .ElseIf(signed_ltz(old_user_principal.get()))
                .Then(
                    # The user has a borrow position
                    calculate_accrued_borrow(old_user_principal, old_user_index, new_pool_borrow_index)
                )
                .Else(
                    # The user has a lend position
                    calculate_accrued_lend(old_user_principal, old_user_index, new_pool_lend_index)
                )
            ),

            ###############################################################################################################
            # 3
            # Transfer between the user and the pool

            # 3.0 Validate user's position against pool size
            Assert(new_pool_liquidity.get() >= signed_max(Int(0), new_user_principal.get())),
            # NOTE: The case for the user repaying more than the pool has borrowed is handled below
            #       in order to handle zero-interest borrow case

            # 3.1 Updates the pool borrowed and liquitiy amounts

            # 3.1.1 Decompose the transfer_amount into borrowed_transfer and liquidity_transfer
            #       such that:
            #         a. transfer_amount == borrowed_transfer + liquidity_transfer
            #         b. sign(transfer_amount) == sign(borrowed_transfer) == sign(liquidity_transfer)
            #         c. if transfer_amount <=0:
            #               # User cannot redeem more than its long position
            #               liquidity_transfer = max(transfer_amount, min(0, -new_user_principal))
            #            else:
            #               # User must repay before subscribing
            #               liquidity_transfer = max(transfer_amount + min(0, new_user_principal), 0)
            #
            #  In other words:
            #  - If transfer_amount is negative, then liquidity_transfer represents the
            #  amount that the user is redeeming from the pool, and borrowed_transfer the amount that is
            #  borrowing from the pool.
            #  - If transfer_amount is positive, then liquidity_transfer represents the
            #  amount that the user is subscribing to the pool, and borrowed_transfer the amount that is
            #  repaying to the pool.
            liquidity_transfer.set(
                signed_max(
                    signed_add(
                        transfer_amount.get(),
                        signed_min(Int(0), new_user_principal.get())
                    ),
                    signed_min(Int(0), signed_neg(new_user_principal.get()))
                )
            ),
            borrowed_transfer.set(
                signed_sub(
                    transfer_amount.get(),
                    liquidity_transfer.get()
                )
            ),

            # 3.1.2 Applies the liquidity_transfer and borrowed_transfer to the pool
            new_pool_borrowed.set(signed_sub(new_pool_borrowed.get(), borrowed_transfer.get())),

            # Handles the case where the user repays more than the pool has borrowed
            # This will happen when there are accumulated microunits of interest
            If(signed_ltz(new_pool_borrowed.get())).Then(
                # Remainder is whatever is left in the transfer after repaying all pool borrows
                remainder.set(signed_neg(new_pool_borrowed.get())),

                # New liquidity index is updated to reflect the remainder
                # liquidity_index' = liquidity_index + liquidity_index * remainder / pool_liquidity
                new_pool_lend_index.set(new_pool_lend_index.get() + WideRatio([new_pool_lend_index.get(), remainder.get()], [new_pool_liquidity.get()])),

                # New liquidity includes the remainder
                new_pool_liquidity.set(signed_add(new_pool_liquidity.get(), remainder.get())),

                # Borrowed is cleared to remain always positive
                new_pool_borrowed.set(Int(0))
            ),

            new_pool_liquidity.set(signed_add(new_pool_liquidity.get(), liquidity_transfer.get())),

            # 3.1.3 Validate the pool has sufficient liquidity to perform the operation
            Assert(new_pool_liquidity.get() >= new_pool_borrowed.get()),

            # 3.2 Update user's principal and cash
            new_user_principal.set(signed_add(new_user_principal.get(), transfer_amount.get())),
            new_user_cash.set(signed_sub(old_user_cash.get(), transfer_amount.get())),
            Assert(Not(signed_ltz(new_user_cash.get()))),

            # 3.3 Update user's index
            new_user_index.set(
                If(signed_ltz(new_user_principal.get()))
                .Then(new_pool_borrow_index.get())
                .Else(new_pool_lend_index.get())
            ),

            # Update user
            user_position.set(new_user_cash, new_user_principal, new_user_index),
            cast(Expr, LocalStateHandler.set_position(account, instrument_id, user_position)),
        ),

        # Update liquidity pool
        new_instrument_state.set(
            asset_id,
            initial_haircut,
            initial_margin,
            maintenance_haircut,
            maintenance_margin,
            new_pool_last_update_time,
            new_pool_borrow_index,
            new_pool_lend_index,
            optimal_utilization_ratio,
            min_rate,
            opt_rate,
            max_rate,
            new_pool_borrowed,
            new_pool_liquidity,
        ),

        # Update instrument
        cast(Expr, GlobalStateHandler.set_instrument(instrument_id, new_instrument_state)),
    )
