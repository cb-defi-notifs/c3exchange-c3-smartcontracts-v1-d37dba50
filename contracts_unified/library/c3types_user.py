"""Types used by the user proxy contract to send operations to C3 core"""

from typing import Literal as L
from typing import TypeAlias

from pyteal import Int, abi

from .c3types import (
    AccountAddress,
    Amount,
    InstrumentId,
    SignedAmount,
    SignedInstrumentBasket,
    Timestamp,
    WormholeAddress,
)


# --- Operation IDs ---
class OperationId:
    """ID numbers for operations"""

    Deposit = Int(0)  # NOTE: This will never be used, deposits don't use signed data
    Withdraw = Int(1)
    PoolMove = Int(2)
    Delegate = Int(3)
    Liquidate = Int(4)
    AccountMove = Int(5)
    Settle = Int(6)


# --- Signing methods ---
class SigningMethod:
    """ID numbers for signing methods"""

    Ed25519 = Int(0)
    EcdsaSecp256k1 = Int(1)


# --- General purpose type aliases ---
AbiOperationId: TypeAlias = abi.Byte
AbiSigningMethod: TypeAlias = abi.Uint8
Signature: TypeAlias = abi.DynamicBytes


# --- User proxy common data ---
class SignedHeader(abi.NamedTuple):
    """
    A signd operation header, decoded as the first N bytes from a operation metadata's data field
    An operation is valid when sent to the given target, during the given lease, which starts
    at the last round following the given timestamp and lasts 1000 rounds.
    """
    # (address,byte[32],uint64)

    target: abi.Field[AccountAddress]
    # TODO: The lease could be computed from the target/timestamp/etc
    lease: abi.Field[abi.StaticBytes[L[32]]]
    last_valid: abi.Field[abi.Uint64]


class OperationMetaData(abi.NamedTuple):
    """A signd operation from the user proxy"""
    # ((address,byte[32],uint64),byte[],byte[],uint8,byte[],address,byte[])

    header: abi.Field[SignedHeader]
    operation: abi.Field[abi.DynamicBytes]
    encoded_signed_data: abi.Field[abi.DynamicBytes]

    signature_method: abi.Field[AbiSigningMethod]
    signature: abi.Field[Signature]
    signer: abi.Field[AccountAddress]
    data_prefix: abi.Field[abi.DynamicBytes]


DelegationChain: TypeAlias = abi.DynamicArray[OperationMetaData]


# --- Operation data for withdraw ---
class WithdrawData(abi.NamedTuple):
    """Ticket data for Withrawals"""
    # (byte,uint8,uint64,(uint16,address),uint64)

    operation: abi.Field[AbiOperationId]
    instrument: abi.Field[InstrumentId]
    amount: abi.Field[Amount]
    receiver: abi.Field[WormholeAddress]
    max_borrow: abi.Field[Amount]
    max_fees: abi.Field[Amount]


# --- Operation data for pool move ---
class PoolMoveData(abi.NamedTuple):
    """Ticket data for pool move"""
    # (byte,uint8,uint64)

    operation: abi.Field[AbiOperationId]
    instrument: abi.Field[InstrumentId]
    amount: abi.Field[SignedAmount]


# --- Delegation data ---
class DelegationData(abi.NamedTuple):
    """Data used to check for delegation"""
    # (byte,address,uint64,uint64)

    operation: abi.Field[AbiOperationId]
    delegate: abi.Field[AccountAddress]
    created: abi.Field[Timestamp]
    expires: abi.Field[Timestamp]


# --- Liquidation Data ---
class LiquidationData(abi.NamedTuple):
    """Holds on-chain liquidation information"""
    # (byte,address,(uint8,uint64)[],(uint8,uint64)[])

    # NOTE: The baskets are the amount the liquidator is taking from the liquidatee
    #       i.e. positive numbers always increase the liquidator's health
    # NOTE: The assets basket must be all positive, but is signed due to pyteal limitations
    operation: abi.Field[AbiOperationId]
    liquidatee: abi.Field[AccountAddress]
    cash: abi.Field[SignedInstrumentBasket]
    pool: abi.Field[SignedInstrumentBasket]


# --- Account Move Data ---
class AccountMoveData(abi.NamedTuple):
    """Data for moving assets and liabilities between accounts"""
    # (byte,address,(uint8,uint64)[],(uint8,uint64)[])

    # NOTE: Both baskets must be all positive, but are signed due to pyteal limitations
    operation: abi.Field[AbiOperationId]
    destination_account: abi.Field[AccountAddress]
    cash: abi.Field[SignedInstrumentBasket]
    pool: abi.Field[SignedInstrumentBasket]


# --- Operation data for settle ---
class OrderData(abi.NamedTuple):
    """Ticket data for settle/add_order"""
    # (byte,address,uint64,uint64,uint8,uint64,uint64,uint8,uint64,uint64)

    operation: abi.Field[AbiOperationId]

    account: abi.Field[abi.Address]
    nonce: abi.Field[abi.Uint64]
    expiration_time: abi.Field[Timestamp]

    sell_instrument: abi.Field[InstrumentId]
    sell_amount: abi.Field[Amount]
    max_borrow_amount: abi.Field[Amount]

    buy_instrument: abi.Field[InstrumentId]
    buy_amount: abi.Field[Amount]
    max_repay_amount: abi.Field[Amount]
