"""Performs liquidation of a user's position"""

from typing import cast

from pyteal import ABIReturnSubroutine, Assert, Expr, For, If, Int, Not, Seq, abi

from contracts_unified.core.internal.health_check import health_check
from contracts_unified.core.internal.liquidation_calculator import (
    calculate_basket_value,
    closer_to_zero,
    scale_basket,
)
from contracts_unified.core.internal.move import signed_account_move_baskets
from contracts_unified.core.internal.perform_pool_move import perform_pool_move
from contracts_unified.core.internal.setup import setup
from contracts_unified.core.internal.validate_sender import sender_is_sig_validator
from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.core.state_handler.local_handler import LocalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    ExcessMargin,
    InstrumentId,
    LiquidationFactors,
    Price,
    Ratio,
    SignedInstrumentBasket,
    UserInstrumentData,
)
from contracts_unified.library.c3types_user import (
    DelegationChain,
    LiquidationData,
    OperationId,
    OperationMetaData,
)
from contracts_unified.library.math import unsigned_min
from contracts_unified.library.signed_math import signed_abs, signed_ltz, signed_neg


@ABIReturnSubroutine
def perform_netting(
    liquidatee: AccountAddress,
    liquidator: AccountAddress
) -> Expr:
    """Performs netting on the account"""

    count = abi.Uint64()
    i = InstrumentId()

    cash_amount = Amount()
    pool_data = UserInstrumentData()
    pool_amount = Amount()

    repay_amount = Amount()

    abi_zero_int = abi.Uint64()

    return Seq(
        abi_zero_int.set(Int(0)),
        # For each instrument, do netting and update the instrument index
        count.set(LocalStateHandler.get_user_instrument_count(liquidatee)),
        For(i.set(Int(0)), i.get() < count.get(), i.set(i.get() + Int(1))).Do(
            # Load data
            pool_data.set(cast(abi.ReturnedValue, LocalStateHandler.get_position(liquidatee, i))),
            cash_amount.set(pool_data.cash),
            pool_amount.set(pool_data.principal),

            # Check if we can update the instrument index
            If(pool_amount.get() != Int(0))
            .Then(
                # Repay only if owed
                If(signed_ltz(pool_amount.get()))
                .Then(
                    # Repay the minimum of the the amount possessed or the amount owed
                    repay_amount.set(unsigned_min(cash_amount.get(), signed_neg(pool_amount.get())))
                ).Else(
                    repay_amount.set(Int(0))
                ),

                # Perform pool move
                cast(Expr, perform_pool_move(liquidatee, i, repay_amount)),
                cast(Expr, perform_pool_move(liquidator, i, abi_zero_int)),
            )
        ),
    )


@ABIReturnSubroutine
def liquidate(
    liquidator_account: AccountAddress,
    user_op: OperationMetaData,
    _delegation_chain: DelegationChain,
    _server_data: abi.DynamicBytes,
    opup_budget: Amount,
) -> Expr:
    """Performs liquidation of a user's position"""

    # Constants
    abi_false = abi.Bool()
    abi_true = abi.Bool()
    abi_zero = Ratio()

    # Liquidation data
    data = LiquidationData()

    liquidatee_account = AccountAddress()
    liquidatee_maint_health = ExcessMargin()

    cash = abi.make(SignedInstrumentBasket)
    pool = abi.make(SignedInstrumentBasket)

    liquidator_health = ExcessMargin()

    factors = LiquidationFactors()
    cash_factor = Ratio()
    pool_factor = Ratio()

    cash_take_value = Price()
    pool_take_value = Price()
    pool_give_value = Price()

    alpha_numerator = ExcessMargin()
    alpha_denominator = ExcessMargin()

    return Seq(
        setup(opup_budget.get()),

        # Set constants
        abi_false.set(Int(0)),
        abi_true.set(Int(1)),
        abi_zero.set(Int(0)),

        # Validate sender is a user proxy
        cast(Expr, sender_is_sig_validator()),

        # Extract liquidation data
        user_op.operation.use(lambda op_data:
            Seq(
                data.decode(op_data.get()),
                data.operation.use(lambda op: Assert(op.get() == OperationId.Liquidate)),
                data.liquidatee.store_into(liquidatee_account),
                data.cash.store_into(cash),
                data.pool.store_into(pool),
            )
        ),

        # Validate liquidatee is not liquidator
        Assert(liquidatee_account.get() != liquidator_account.get()),

        # Validate liquidatee is liquidatable
        liquidatee_maint_health.set(health_check(liquidatee_account, abi_true)),
        Assert(signed_ltz(liquidatee_maint_health.get())),

        # Perform netting on liquidatee account
        cast(Expr, perform_netting(liquidatee_account, liquidator_account)),

        # Get global constants
        factors.decode(GlobalStateHandler.get_liquidation_factors()),
        cash_factor.set(factors.cash_liquidation_factor),
        pool_factor.set(factors.pool_liquidation_factor),

        # Check the closer-to-zero condition for the pool basket
        cast(Expr, closer_to_zero(liquidatee_account, pool)),

        # Calculate basket values
        # NOTE: The cash_take_value and pool_give_value use the cash_factor, where as the pool_take_value uses the pool_factor
        #       See the formulas from the design doc for more info.
        cash_take_value.set(calculate_basket_value(cash, abi_false, cash_factor, abi_true, abi_true, abi_false)),
        pool_take_value.set(calculate_basket_value(pool, abi_false, pool_factor, abi_true, abi_true, abi_false)),
        pool_give_value.set(calculate_basket_value(pool, abi_true, cash_factor, abi_true, abi_false, abi_false)),

        # Check inequality is satisfied
        Assert(cash_take_value.get() + pool_take_value.get() <= pool_give_value.get()),

        # Ensure fairness by calculating alpha and scaling the baskets
        # alpha = health(initial) / (initial_haircut * take_assets * price + initial_haircut * (1 - opt_util) * take_liabilities * price - (1 + initial_margin) * give_liabilities * price)
        # NOTE: health_check sets up the local state handler for itself, so we don't need to
        # NOTE: Reusing the above variables for the values used when calculating the denominator
        alpha_numerator.set(health_check(liquidatee_account, abi_false)),
        cash_take_value.set(calculate_basket_value(cash, abi_false, abi_zero, abi_false, abi_false, abi_false)),
        pool_take_value.set(calculate_basket_value(pool, abi_false, abi_zero, abi_false, abi_false, abi_true)),
        pool_give_value.set(calculate_basket_value(pool, abi_true, abi_zero, abi_false, abi_true, abi_false)),
        alpha_denominator.set(pool_give_value.get() - (cash_take_value.get() + pool_take_value.get())),

        # Clamp alpha to be between 0 and 1
        alpha_numerator.set(signed_abs(alpha_numerator.get())),

        If(alpha_numerator.get() > alpha_denominator.get())
        .Then(alpha_numerator.set(alpha_denominator.get())),

        # Scale the basket values to be fair
        cash.set(cast(abi.ReturnedValue, scale_basket(cash, alpha_numerator, alpha_denominator))),
        pool.set(cast(abi.ReturnedValue, scale_basket(pool, alpha_numerator, alpha_denominator))),

        # Perform liquidation swaps, all relevant glboal indexes are updated after netting
        cast(Expr, signed_account_move_baskets(liquidatee_account, liquidator_account, cash, pool, abi_false, abi_true)),

        # Verify liquidator is still healthy
        # NOTE: Liquidator must always be in the green after liquidation
        # NOTE: Liquidatee will always be healthier by design
        liquidator_health.set(health_check(liquidator_account, abi_false)),
        Assert(Not(signed_ltz(liquidator_health.get()))),
    )
