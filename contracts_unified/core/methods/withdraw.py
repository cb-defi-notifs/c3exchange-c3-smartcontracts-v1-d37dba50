"""
Implements Core contract method for withdrawing funds from a user's balance
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
    Not,
    Seq,
    TxnField,
    TxnType,
    abi,
)

from contracts_unified.core.internal.health_check import health_check
from contracts_unified.core.internal.move import collect_fees, signed_add_to_cash
from contracts_unified.core.internal.perform_pool_move import perform_pool_move
from contracts_unified.core.internal.setup import setup
from contracts_unified.core.internal.validate_sender import sender_is_sig_validator
from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.core.state_handler.local_handler import LocalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    AssetId,
    InstrumentId,
    InstrumentListElement,
    SignedAmount,
    UserInstrumentData,
    WormholeAddress,
)
from contracts_unified.library.c3types_server import WithdrawExtraData
from contracts_unified.library.c3types_user import (
    DelegationChain,
    OperationId,
    OperationMetaData,
    WithdrawData,
)
from contracts_unified.library.constants import ALGORAND_CHAIN_ID
from contracts_unified.library.signed_math import signed_ltz, signed_neg


@ABIReturnSubroutine
def submit_withdraw_onchain(
    address: AccountAddress,
    instrument_id: InstrumentId,
    amount: Amount,
) -> Expr:
    """Submits a widthdrawal transaction to the Algorand network"""

    asset_id = AssetId()
    element = InstrumentListElement()

    return Seq(
        # Get the asset ID
        # NOTE: GlobalStateHandler and Blob _must_ be initialized before this call
        element.set(cast(abi.ReturnedValue, GlobalStateHandler.get_instrument(instrument_id))),
        asset_id.set(element.asset_id),

        # Send funds to target address
        If(asset_id.get() == Int(0))
        .Then(
            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.fee: Int(0),
                    TxnField.amount: amount.get(),
                    TxnField.receiver: address.get(),
                }
            )
        )
        .Else(
            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.fee: Int(0),
                    TxnField.xfer_asset: asset_id.get(),
                    TxnField.asset_amount: amount.get(),
                    TxnField.asset_receiver: address.get(),
                }
            )
        ),
    )


@ABIReturnSubroutine
def submit_withdraw_offchain(
    withdraw_buffer: abi.Address,
    instrument_id: InstrumentId,
    amount: abi.Uint64,
) -> Expr:
    """Submits a withdraw via wormhole"""
    asset_id = AssetId()
    element = InstrumentListElement()
    return Seq(
        # Send funds to the Wormhole withdraw buffer.
        # The 'completeTransfer' Wormhole app call will do the final transfer
        # from the buffer to the token bridge.
        element.set(cast(abi.ReturnedValue, GlobalStateHandler.get_instrument(instrument_id))),
        asset_id.set(element.asset_id),
        If(asset_id.get() == Int(0))
        .Then(
            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.fee: Int(0),
                    TxnField.amount: amount.get(),
                    TxnField.receiver: withdraw_buffer.get(),
                }
            )
        )
        .Else(
            InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.fee: Int(0),
                    TxnField.xfer_asset: asset_id.get(),
                    TxnField.asset_amount: amount.get(),
                    TxnField.asset_receiver: withdraw_buffer.get(),
                }
            )
        ),
    )

@ABIReturnSubroutine
def withdraw(
    account: AccountAddress,
    user_op: OperationMetaData,
    delegation_chain: DelegationChain,
    server_params: WithdrawExtraData,
    opup_budget: Amount,
) -> Expr:
    """Withdraws funds from a user and sends them to a given Wormhole or Algorand address, depending on target chain

    Args:

        account (AccountAddress): The user account address.
        user_op (OperationMetaData): The user operation metadata. This contains signed withdraw data: instrument, amount, receiver, and maximum amount to borrow.
        delegation_chain (DelegationChain): The delegation chain. For withdraw operations this must be empty.
        server_params (abi.Uint64): The server parameters. For withdraw, this parameter just contains server' own balance.
        opup_budget (Amount): Additional computation budget for the operation.

    """

    # Holds the withdraw buffer address
    wormhole_withdraw_buffer = abi.Address()

    # Constants
    abi_false = abi.Bool()

    # Holds extracted withdraw data from the user_op
    withdraw_data = WithdrawData()

    # Holds extracted withdraw data from the user_op
    instrument_id = InstrumentId()
    amount = Amount()
    receiver = WormholeAddress()
    max_borrow = Amount()
    amount_to_deduct = SignedAmount()
    amount_to_withdraw = SignedAmount()
    amount_to_borrow = SignedAmount()
    max_fees = Amount()

    # User balance, to calculate the cash/pool split of the withdrawal
    position = UserInstrumentData()
    balance = Amount()

    # Fees to be collected
    withdraw_fee = Amount()

    # Used to validate the user's health
    user_health = abi.Uint64()

    return Seq(
        setup(opup_budget.get()),

        # Load constants
        abi_false.set(Int(0)),

        # Validate sender is a user proxy
        cast(Expr, sender_is_sig_validator()),

        # No delegation is allowed for withdraw
        Assert(delegation_chain.length() == Int(0)),

        # Decode and extract withdraw operation
        user_op.operation.use(lambda op_data:
            Seq(
                withdraw_data.decode(op_data.get()),
                withdraw_data.operation.use(lambda op: Assert(op.get() == OperationId.Withdraw)),
                withdraw_data.instrument.store_into(instrument_id),
                withdraw_data.amount.store_into(amount),
                withdraw_data.receiver.store_into(receiver),
                withdraw_data.max_borrow.store_into(max_borrow),
                withdraw_data.max_fees.store_into(max_fees),
            )
        ),

        # Calculate cash and pool withdrawal amounts
        position.set(cast(abi.ReturnedValue, LocalStateHandler.get_position(account, instrument_id))),
        balance.set(position.cash),
        server_params.locked_cash.use(lambda locked_cash:
            balance.set(balance.get() - locked_cash.get()),
        ),

        # Get the fees
        withdraw_fee.set(server_params.withdraw_fee),

        # Do not exceed maximum fee limit specified in request.
        Assert(withdraw_fee.get() <= max_fees.get()),

        # Validate the user is not borrowing more than they have allowed
        Assert(amount.get() <= max_borrow.get() + balance.get()),

        # Calculate withdrawal amounts
        If(amount.get() > balance.get())
        .Then(
            amount_to_borrow.set(signed_neg(amount.get() - balance.get())),
        )
        .Else(
            amount_to_borrow.set(Int(0)),
        ),
        # This is the delta value to apply to the user cash
        amount_to_deduct.set(signed_neg(amount.get())),
        # This is the amount the user will actually get, implicitly fails if fees are bigger than the amount
        amount_to_withdraw.set(amount.get() - withdraw_fee.get()),

        # Borrow if needed
        If(amount_to_borrow.get() != Int(0))
        .Then(cast(Expr, perform_pool_move(account, instrument_id, amount_to_borrow))),

        # Remove assets
        cast(Expr, signed_add_to_cash(account, instrument_id, amount_to_deduct)),

        # Pay fees
        cast(Expr, collect_fees(instrument_id, withdraw_fee)),

        # Validate user is still healthy
        # NOTE: Withdraw always makes the user less healthy, so we don't need to check
        #       the user's health before the withdrawal
        user_health.set(health_check(account, abi_false)),
        Assert(Not(signed_ltz(user_health.get()))),

        # Now that assets/liabilities are up to date, send out payment transaction.
        # If we are withdrawing to offchain, we need to check wormhole transactions
        wormhole_withdraw_buffer.set(GlobalStateHandler.get_withdraw_buffer()),
        receiver.chain_id.use(lambda chain_id:
            receiver.address.use(lambda address:
                If(
                    chain_id.get() == Int(ALGORAND_CHAIN_ID),
                    cast(Expr, submit_withdraw_onchain(address, instrument_id, amount_to_withdraw)),
                    cast(Expr, submit_withdraw_offchain(wormhole_withdraw_buffer, instrument_id, amount_to_withdraw)),
                )
            )
        ),
    )
