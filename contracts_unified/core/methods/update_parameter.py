"""
Implements Core contract method for changing a global parameter
"""

from pyteal import (
    ABIReturnSubroutine,
    Assert,
    Cond,
    Expr,
    Global,
    If,
    ScratchVar,
    Seq,
    TealType,
    Txn,
    abi,
)

from contracts_unified.core.state_handler.global_handler import (
    KEY_FEE_TARGET,
    KEY_LIQUIDATION_FACTORS,
    KEY_OPERATOR_ADDRESS,
    KEY_PRICECASTER_ID,
    KEY_QUANT_ADDRESS,
    KEY_SIGNATURE_VALIDATOR,
    KEY_WITHDRAW_BUFFER,
    KEY_WORMHOLE_BRIDGE_ID,
    GlobalStateHandler,
)


@ABIReturnSubroutine
def update_parameter(
    key_to_update: abi.DynamicBytes,
    updated_value: abi.DynamicBytes,
) -> Expr:
    """Implements the method that changes a global parameter of the contract.

    Arguments:

    key_to_update (abi.DynamicBytes): Key of the parameter to update
    updated_value (abi.DynamicBytes): New value of the parameter

    """

    key = ScratchVar(TealType.bytes)
    value = ScratchVar(TealType.bytes)

    return Seq(
        key.store(key_to_update.get()),
        value.store(updated_value.get()),
        If(key.load() == KEY_LIQUIDATION_FACTORS).Then(
            Assert(GlobalStateHandler.get_quant_address() == Txn.sender()),
            GlobalStateHandler.set_liquidation_factors(value.load())
        ).Else(
            Assert(Global.creator_address() == Txn.sender()),
            Cond(
                [key.load() == KEY_PRICECASTER_ID, GlobalStateHandler.set_pricecaster_id(value.load())],
                [key.load() == KEY_WORMHOLE_BRIDGE_ID, GlobalStateHandler.set_wormhole_bridge_id(value.load())],
                [key.load() == KEY_SIGNATURE_VALIDATOR, GlobalStateHandler.set_signature_validator(value.load())],
                [key.load() == KEY_QUANT_ADDRESS, GlobalStateHandler.set_quant_address(value.load())],
                [key.load() == KEY_FEE_TARGET, GlobalStateHandler.set_fee_target(value.load())],
                [key.load() == KEY_WITHDRAW_BUFFER, GlobalStateHandler.set_withdraw_buffer(value.load())],
                [key.load() == KEY_OPERATOR_ADDRESS, GlobalStateHandler.set_operator_address(value.load())],
            )
        )
    )
