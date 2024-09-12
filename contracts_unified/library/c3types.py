"""
Declares types used in C3 Core contract.
"""
from typing import Literal as L
from typing import TypeAlias

from pyteal.ast import abi

# --- General purpose type aliases ---
# Two Complement encoded signed 64-bit integer
Sint64: TypeAlias = abi.Uint64
# Ratios are represented as the ratio multiplied by RATIO_ONE
Ratio: TypeAlias = abi.Uint16
# Rates are represented as the rate multiplied by RATE_ONE
InterestRate: TypeAlias = abi.Uint64
# A timestamp is a unix timestamp
Timestamp: TypeAlias = abi.Uint64
# A relative timestamp is a unix timestamp minus the contract init timestamp
RelativeTimestamp: TypeAlias = abi.Uint32
# An index into the instrument list on the core contract global state
InstrumentId: TypeAlias = abi.Uint8
# The hash of an order's data with the prefix ORDER_PREFIX
# NOTE: This must be kept in sync, len(SHA_512_256) + len(ORDER_PREFIX) = 37
OrderId: TypeAlias = abi.StaticBytes[L[37]]
# An amount is a raw count of the number of units of a given instrument. This is always positive.
Amount: TypeAlias = abi.Uint64
# A price is measured in pico(1E-12) dollars per unit
Price: TypeAlias = abi.Uint64
# A rescaled price a price rescaled by PRICECASTER_RESCALE_FACTOR to have less precision
RescaledPrice: TypeAlias = abi.Uint64
# A signed amount is an amount that can be negative
SignedAmount: TypeAlias = Sint64
# An algorand asset ID
AssetId: TypeAlias = abi.Uint64
# An algorand application ID
AppId: TypeAlias = abi.Uint64
# A Wormhole chain ID
ChainId: TypeAlias = abi.Uint16
# The address (Public key) of a user
AccountAddress: TypeAlias = abi.Address
# The result type of a health calculation
ExcessMargin: TypeAlias = abi.Uint64
# The word "DEPOSIT"
DepositWord: TypeAlias = abi.StaticBytes[L[7]]
# An Application id encoded in bytes
EncodedAppId: TypeAlias = abi.StaticBytes[L[8]]
# Liquidation Factors encoded in bytes
EncodedLiquidationFactors: TypeAlias = abi.StaticBytes[L[4]]
# Boolean
Boolean: TypeAlias = abi.Uint64

class SignedInstrumentAmount(abi.NamedTuple):
    """Holds an instrument and an amount"""

    instrument: abi.Field[InstrumentId]
    amount: abi.Field[SignedAmount]


SignedInstrumentBasket: TypeAlias = abi.DynamicArray[SignedInstrumentAmount]

class LiquidationFactors(abi.NamedTuple):
    """Holds the liquidation factors"""

    cash_liquidation_factor: abi.Field[Ratio]       # 2 bytes
    pool_liquidation_factor: abi.Field[Ratio]       # 2 bytes

class InstrumentListElement(abi.NamedTuple):
    """Used in global instrument box (i) to hold a collection of instrument info"""

    # Algorand ASA ID for the instrument's underlying asset
    asset_id: abi.Field[AssetId]

    # The initial and maintenance risk factors for the instrument
    initial_haircut: abi.Field[Ratio]
    initial_margin: abi.Field[Ratio]
    maintenance_haircut: abi.Field[Ratio]
    maintenance_margin: abi.Field[Ratio]

    # The last time the pool was updated
    last_update_time: abi.Field[RelativeTimestamp]

    # The pool's borrow/lend indexes
    borrow_index: abi.Field[abi.Uint64]
    lend_index: abi.Field[abi.Uint64]

    # The pool's interest curve parameters
    optimal_utilization: abi.Field[Ratio]
    min_rate: abi.Field[InterestRate]
    opt_rate: abi.Field[InterestRate]
    max_rate: abi.Field[InterestRate]

    # Total amount borrowed from the pool
    borrowed: abi.Field[Amount]

    # Total amount lent to the pool
    liquidity: abi.Field[Amount]


# --- Local data ---
class UserInstrumentData(abi.NamedTuple):
    """Used to hold the user's loan data per asset"""

    cash: abi.Field[Amount]
    principal: abi.Field[SignedAmount]
    index: abi.Field[abi.Uint64]


# --- Order Data ---
class OnChainOrderData(abi.NamedTuple):
    """Holds on-chain order information"""

    sell_remaining: abi.Field[Amount]
    borrow_remaining: abi.Field[Amount]
    repay_remaining: abi.Field[Amount]


# --- Wormhole data ---
class WormholeAddress(abi.NamedTuple):
    """Holds a wormhole address"""

    chain_id: abi.Field[ChainId]
    address: abi.Field[AccountAddress]


class DecodedWormholePayload(abi.NamedTuple):
    """Holds decoded Wormhole payload fields"""

    amount: abi.Field[Amount]
    receiver: abi.Field[abi.Address]
    repay_amount: abi.Field[Amount]
