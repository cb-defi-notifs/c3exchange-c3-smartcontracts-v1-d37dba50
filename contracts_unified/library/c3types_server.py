"""Types used by the server to interact with the C3 core contract"""


from pyteal import abi

from .c3types import Amount, AssetId, Boolean, InstrumentId, InterestRate, Ratio


# --- Server update_instrument and create data ---
class UpdateInstrumentInfo(abi.NamedTuple):
    """Used to create a new instrument"""

    instrument_id: abi.Field[InstrumentId]
    asset_id: abi.Field[AssetId]
    initial_haircut: abi.Field[Ratio]
    initial_margin: abi.Field[Ratio]
    maintenance_haircut: abi.Field[Ratio]
    maintenance_margin: abi.Field[Ratio]
    optimal_utilization: abi.Field[Ratio]
    min_rate: abi.Field[InterestRate]
    opt_rate: abi.Field[InterestRate]
    max_rate: abi.Field[InterestRate]


class SettleExtraData(abi.NamedTuple):
    """Holds server data for the settle function"""
    # (uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64)

    buyer_fees: abi.Field[Amount]
    buyer_to_send: abi.Field[Amount]
    buyer_to_borrow: abi.Field[Amount]
    buyer_to_repay: abi.Field[Amount]
    buyer_negative_margin: abi.Field[Boolean]

    seller_fees: abi.Field[Amount]
    seller_to_send: abi.Field[Amount]
    seller_to_borrow: abi.Field[Amount]
    seller_to_repay: abi.Field[Amount]
    seller_negative_margin: abi.Field[Boolean]

class WithdrawExtraData(abi.NamedTuple):
    """Holds server data for the withdraw function"""
    # (uint64,uint64)

    locked_cash: abi.Field[Amount]
    withdraw_fee: abi.Field[Amount]
