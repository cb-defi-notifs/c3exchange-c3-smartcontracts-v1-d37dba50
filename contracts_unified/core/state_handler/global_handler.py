"""Implements core contract global state handler"""

from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    App,
    Assert,
    Btoi,
    Bytes,
    Expr,
    Global,
    Int,
    Len,
    MinBalance,
    Pop,
    Seq,
    abi,
)

from contracts_unified.library.c3types import (
    InstrumentId,
    InstrumentListElement,
    LiquidationFactors,
)
from contracts_unified.library.constants import ADDRESS_SIZE

KEY_INIT_TIMESTAMP = Bytes("t")
KEY_INSTRUMENT_COUNT = Bytes("c")
KEY_MBR_FUND = Bytes("m")
KEY_PRICECASTER_ID = Bytes("p")
KEY_WORMHOLE_BRIDGE_ID = Bytes("b")
KEY_LIQUIDATION_FACTORS = Bytes("l")
KEY_SIGNATURE_VALIDATOR = Bytes("s")
KEY_WITHDRAW_BUFFER = Bytes("w")
KEY_QUANT_ADDRESS = Bytes("q")
KEY_OPERATOR_ADDRESS = Bytes("o")
KEY_FEE_TARGET = Bytes("f")


class GlobalStateHandler:
    """Global state handler"""

    instrument_size = abi.make(InstrumentListElement).type_spec().byte_length_static()
    max_instrument_count = 80

    # NOTE: Most of these methods are not subroutines for performance reasons
    @staticmethod
    def initialize() -> Expr:
        """Initialize the global blob"""

        return Pop(App.box_create(Bytes("i"), Int(GlobalStateHandler.instrument_size * GlobalStateHandler.max_instrument_count)))

    @staticmethod
    def get_relative_timestamp() -> Expr:
        """Gets the relative timestamp"""

        return Global.latest_timestamp() - App.globalGet(KEY_INIT_TIMESTAMP)

    @staticmethod
    def set_init_timestamp() -> Expr:
        """Sets the initial timestamp"""

        return App.globalPut(KEY_INIT_TIMESTAMP, Global.latest_timestamp())

    @staticmethod
    def get_instrument_count() -> Expr:
        """Gets the number of instruments"""

        return App.globalGet(KEY_INSTRUMENT_COUNT)

    @staticmethod
    def set_instrument_count(instrument_count) -> Expr:
        """Sets the number of instruments"""

        return App.globalPut(KEY_INSTRUMENT_COUNT, instrument_count)

    @staticmethod
    def get_pricecaster_id() -> Expr:
        """Gets the App id of the pricecaster"""

        return App.globalGet(KEY_PRICECASTER_ID)

    @staticmethod
    def set_pricecaster_id(pricecaster_id) -> Expr:
        """Sets the App id of the pricecaster"""

        return App.globalPut(KEY_PRICECASTER_ID, Btoi(pricecaster_id))

    @staticmethod
    def get_wormhole_bridge_id() -> Expr:
        """Gets the App id of the wormhole bridge"""

        return App.globalGet(KEY_WORMHOLE_BRIDGE_ID)

    @staticmethod
    def set_wormhole_bridge_id(wormhole_bridge_id) -> Expr:
        """Sets the App id of the wormhole bridge"""

        return App.globalPut(KEY_WORMHOLE_BRIDGE_ID, Btoi(wormhole_bridge_id))

    @staticmethod
    @ABIReturnSubroutine
    def set_address(key, address) -> Expr:
        """Sets an address in the global storage checking the length"""

        return Seq(
            Assert(Len(address) == Int(ADDRESS_SIZE)),
            App.globalPut(key, address)
        )

    @staticmethod
    def get_signature_validator() -> Expr:
        """Checks the address of the signature validator"""

        return App.globalGet(KEY_SIGNATURE_VALIDATOR)

    @staticmethod
    def set_signature_validator(signature_validator) -> Expr:
        """Sets the address of the signature validator"""

        return cast(Expr, GlobalStateHandler.set_address(KEY_SIGNATURE_VALIDATOR, signature_validator))

    @staticmethod
    def get_operator_address() -> Expr:
        """Gets the address of the operator"""

        return App.globalGet(KEY_OPERATOR_ADDRESS)

    @staticmethod
    def set_operator_address(operator_address) -> Expr:
        """Sets the address of the operator"""

        return cast(Expr, GlobalStateHandler.set_address(KEY_OPERATOR_ADDRESS, operator_address))

    @staticmethod
    def get_quant_address() -> Expr:
        """Gets the quant address"""

        return App.globalGet(KEY_QUANT_ADDRESS)

    @staticmethod
    def set_quant_address(quant_address) -> Expr:
        """Sets the quant address"""

        return cast(Expr, GlobalStateHandler.set_address(KEY_QUANT_ADDRESS, quant_address))

    @staticmethod
    def get_fee_target() -> Expr:
        """Gets the fee target address"""

        return App.globalGet(KEY_FEE_TARGET)

    @staticmethod
    def set_fee_target(fee_target_address) -> Expr:
        """Sets the fee target address"""

        return cast(Expr, GlobalStateHandler.set_address(KEY_FEE_TARGET, fee_target_address))

    @staticmethod
    def get_withdraw_buffer() -> Expr:
        """Gets the withdraw buffer address"""

        return App.globalGet(KEY_WITHDRAW_BUFFER)

    @staticmethod
    def set_withdraw_buffer(withdraw_buffer) -> Expr:
        """Sets the withdraw buffer address"""

        return cast(Expr, GlobalStateHandler.set_address(KEY_WITHDRAW_BUFFER, withdraw_buffer))

    @staticmethod
    @ABIReturnSubroutine
    def ensure_mbr_fund() -> Expr:
        """Ensures the current mbr is lower than the fund"""

        return Assert(MinBalance(Global.current_application_address()) <= App.globalGet(KEY_MBR_FUND))

    @staticmethod
    def add_mbr_fund(mbr_fund) -> Expr:
        """Increments the mbr fund amount by an amount"""

        return App.globalPut(KEY_MBR_FUND, App.globalGet(KEY_MBR_FUND) + mbr_fund)

    @staticmethod
    def get_liquidation_factors() -> Expr:
        """Gets the object representing the liquidation factors"""

        return App.globalGet(KEY_LIQUIDATION_FACTORS)

    @staticmethod
    def set_liquidation_factors(factors) -> Expr:
        """Sets the global liquidation factors"""
        factors_size = abi.make(LiquidationFactors).type_spec().byte_length_static()
        return Seq(
            Assert(Len(factors) == Int(factors_size)),
            App.globalPut(KEY_LIQUIDATION_FACTORS, factors),
        )

    @staticmethod
    @ABIReturnSubroutine
    def get_instrument(
        instrument_id: InstrumentId,
        *,
        output: InstrumentListElement,
    ) -> Expr:
        """Get the instrument details for a given instrument ID"""

        return Seq(
            output.decode(App.box_extract(Bytes("i"), instrument_id.get() * Int(GlobalStateHandler.instrument_size), Int(GlobalStateHandler.instrument_size))),
        )

    @staticmethod
    def set_instrument(
        instrument_id: InstrumentId,
        new_entry: InstrumentListElement,
    ) -> Expr:
        """Set the instrument details for a given instrument ID"""

        return Seq(
            App.box_replace(Bytes("i"), instrument_id.get() * Int(GlobalStateHandler.instrument_size), new_entry.encode()),
        )
