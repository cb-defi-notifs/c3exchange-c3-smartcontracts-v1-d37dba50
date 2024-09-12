"""Defines the local state handler for the Core contract."""

from typing import cast

from pyteal import ABIReturnSubroutine, App, Expr, If, Int, Len, Pop, Seq, abi

from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    InstrumentId,
    UserInstrumentData,
)


class LocalStateHandler:
    """Handles per-user state for the Core contract"""

    position_size = abi.make(UserInstrumentData).type_spec().byte_length_static()

    # NOTE: Not a subroutine for performance reasons
    @staticmethod
    def initialize_or_resize_if_required(account: AccountAddress, offset: abi.Uint64) -> Expr:
        """Sets up the box for the given account if it does not exist or needs to be resized"""
        return Seq(
            (box_contents := App.box_get(account.get())),
            # If the box is not big enough, we enlarge it
            If(Len(box_contents.value()) <= offset.get()).Then(
                # Both delete and create work whether the box exists already or not
                Pop(App.box_delete(account.get())),
                Pop(App.box_create(account.get(), offset.get() + Int(LocalStateHandler.position_size))),
                App.box_replace(account.get(), Int(0), box_contents.value()),
                # Ensure we have enough funds for mbr
                cast(Expr, GlobalStateHandler.ensure_mbr_fund()),
            )
        )

    @staticmethod
    @ABIReturnSubroutine
    def get_position(
        account: AccountAddress,
        instrument_id: InstrumentId,
        *,
        output: UserInstrumentData
    ) -> Expr:
        """Returns the cash and pool data for the given instrument ID"""

        offset = abi.Uint64()

        return Seq(
            offset.set(instrument_id.get() * Int(LocalStateHandler.position_size)),
            # NOTE: Initialize the box if it doesn't exist.
            # This should only happen for the fee target if it didn't deposit/initialize itself already
            # To prevent that condition from causing failures, we initialize here
            # We will also resize the box if it's not big enough to hold the required instrument offset
            cast(Expr, LocalStateHandler.initialize_or_resize_if_required(account, offset)),
            output.decode(App.box_extract(account.get(), offset.get(), Int(LocalStateHandler.position_size)))
        )

    # NOTE: Not a subroutine for performance reasons
    @staticmethod
    def set_position(account: AccountAddress, instrument_id: InstrumentId, data: UserInstrumentData) -> Expr:
        """Sets the cash and pool data for the given instrument ID"""
        return App.box_replace(account.get(), instrument_id.get() * Int(LocalStateHandler.position_size), data.encode())

    @staticmethod
    @ABIReturnSubroutine
    def get_user_instrument_count(account: AccountAddress, *, output: abi.Uint64) -> Expr:
        """Gets the amount of instruments allocated for an user"""
        return Seq(
            (box_length := App.box_length(account.get())),
            output.set(box_length.value() / Int(LocalStateHandler.position_size)),
            If(output.get() > GlobalStateHandler.get_instrument_count()).Then(
                output.set(GlobalStateHandler.get_instrument_count())
            )
        )
