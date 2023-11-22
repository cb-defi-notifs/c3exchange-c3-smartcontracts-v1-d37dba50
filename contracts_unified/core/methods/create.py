"""
Implements Core contract creation ABI bare call.
"""
from pyteal import ABIReturnSubroutine, Expr, Int, Seq, abi

from contracts_unified.core.internal.setup import setup
from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.library.c3types import (
    Amount,
    EncodedAppId,
    EncodedLiquidationFactors,
)


@ABIReturnSubroutine
def create(
    pricecaster_id: EncodedAppId,
    wormhole_token_bridge_id: EncodedAppId,
    liquidation_factors: EncodedLiquidationFactors,
    withdraw_buffer_address: abi.Address,
    signature_validator_address: abi.Address,
    operator_address: abi.Address,
    quant_address: abi.Address,
    fee_target_address: abi.Address,
    opup_budget: Amount,
) -> Expr:
    """Implements the contract method called at creation time"""

    return Seq(
        # Generate budget for the call
        setup(opup_budget.get()),

        # Initialize global state
        GlobalStateHandler.set_init_timestamp(),
        GlobalStateHandler.set_instrument_count(Int(0)),
        GlobalStateHandler.set_pricecaster_id(pricecaster_id.get()),
        GlobalStateHandler.set_wormhole_bridge_id(wormhole_token_bridge_id.get()),
        GlobalStateHandler.set_liquidation_factors(liquidation_factors.get()),
        GlobalStateHandler.set_withdraw_buffer(withdraw_buffer_address.get()),
        GlobalStateHandler.set_signature_validator(signature_validator_address.get()),
        GlobalStateHandler.set_operator_address(operator_address.get()),
        GlobalStateHandler.set_quant_address(quant_address.get()),
        GlobalStateHandler.set_fee_target(fee_target_address.get()),
    )
