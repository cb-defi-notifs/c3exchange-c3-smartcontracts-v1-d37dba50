"""
Implements Core contract method for adding an instrument.
"""


from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    Assert,
    Expr,
    Global,
    If,
    InnerTxnBuilder,
    Int,
    Seq,
    Txn,
    TxnField,
    TxnType,
    abi,
)

from contracts_unified.core.internal.perform_pool_move import perform_pool_move
from contracts_unified.core.internal.setup import setup
from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.library.c3types import (
    Amount,
    AssetId,
    InstrumentId,
    InstrumentListElement,
    InterestRate,
    Ratio,
    RelativeTimestamp,
)
from contracts_unified.library.c3types_server import UpdateInstrumentInfo
from contracts_unified.library.constants import RATE_ONE


def inner_asset_opt_in(asset_id: AssetId) -> Expr:
    """Inner transaction that opts in to an ASA"""

    return InnerTxnBuilder.Execute(
        {
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: asset_id.get(),
            TxnField.asset_receiver: Global.current_application_address(),
            TxnField.asset_amount: Int(0),
            TxnField.fee: Int(0),
        }
    )

@ABIReturnSubroutine
def update_instrument(
    info: UpdateInstrumentInfo,
    opup_budget: Amount,
) -> Expr:
    """Implements the method that adds an instrument to the Core contract storage box.

    Arguments:

    info (UpdateInstrumentInfo): Instrument information to add or update.
    opup_budget (Amount): Additional computation budget to allocate to this transaction.

    """

    abi_zero = abi.Uint64()
    abi_rate_one = abi.Uint64()
    abi_zero_address = abi.Address()

    timestamp = RelativeTimestamp()

    asset_id = AssetId()
    initial_haircut = Ratio()
    initial_margin = Ratio()
    maintenance_haircut = Ratio()
    maintenance_margin = Ratio()
    optimal_utilization = Ratio()
    min_rate = InterestRate()
    opt_rate = InterestRate()
    max_rate = InterestRate()
    borrow_index = abi.Uint64()
    lend_index = abi.Uint64()
    borrowed = Amount()
    liquidity = Amount()
    entry = InstrumentListElement()

    instrument_id = InstrumentId()
    instrument_count = abi.Uint64()

    return Seq(
        setup(opup_budget.get()),

        # Validate sender
        Assert(Txn.sender() == GlobalStateHandler.get_quant_address()),

        # Initialize the instrument box first if it doesn't exist
        cast(Expr, GlobalStateHandler.initialize()),

        # Get init time
        timestamp.set(GlobalStateHandler.get_relative_timestamp()),

        # Create the instrument list element
        abi_zero.set(Int(0)),
        abi_rate_one.set(RATE_ONE),
        abi_zero_address.set(Global.zero_address()),

        # Extract fields from info
        asset_id.set(info.asset_id),
        initial_haircut.set(info.initial_haircut),
        initial_margin.set(info.initial_margin),
        maintenance_haircut.set(info.maintenance_haircut),
        maintenance_margin.set(info.maintenance_margin),
        optimal_utilization.set(info.optimal_utilization),
        min_rate.set(info.min_rate),
        opt_rate.set(info.opt_rate),
        max_rate.set(info.max_rate),

        # Load the current instrument count and validate it
        instrument_id.set(info.instrument_id),
        instrument_count.set(GlobalStateHandler.get_instrument_count()),
        Assert(instrument_id.get() <= instrument_count.get()),

        # Validate instrument zero is always algo
        If(instrument_id.get() == Int(0))
        .Then(Assert(asset_id.get() == Int(0))),

        # Check for new entry vs old entry
        If(instrument_id.get() == instrument_count.get())
        .Then(
            # Perform optin to asset if needed
            If(asset_id.get() != Int(0), cast(Expr, inner_asset_opt_in(asset_id))),

            # Create the new entry
            borrow_index.set(abi_rate_one),
            lend_index.set(abi_rate_one),
            borrowed.set(abi_zero),
            liquidity.set(abi_zero),

            # Increase the instrument count
            GlobalStateHandler.set_instrument_count(instrument_count.get() + Int(1)),
        )
        .Else(
            # Not a new instrument, we need to accrue the interest
            cast(Expr, perform_pool_move(abi_zero_address, instrument_id, abi_zero)),
            # Retain the accrued interest values for the new entry
            entry.set(cast(abi.ReturnedValue, GlobalStateHandler.get_instrument(instrument_id))),
            # NOTE: The timestamp should be the same as the one for a new instrument
            entry.borrow_index.store_into(borrow_index),
            entry.lend_index.store_into(lend_index),
            entry.borrowed.store_into(borrowed),
            entry.liquidity.store_into(liquidity),
        ),

        # Create the new entry
        entry.set(
            asset_id,
            initial_haircut,
            initial_margin,
            maintenance_haircut,
            maintenance_margin,
            timestamp,
            borrow_index,
            lend_index,
            optimal_utilization,
            min_rate,
            opt_rate,
            max_rate,
            borrowed,
            liquidity,
        ),

        # Perform update/insert for entry
        GlobalStateHandler.set_instrument(instrument_id, entry),

        # Ensure we have enough funds for mbr
        cast(Expr, GlobalStateHandler.ensure_mbr_fund()),
    )
