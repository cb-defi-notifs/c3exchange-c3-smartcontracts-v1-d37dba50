"""
Provides methods to validate the sender of a transaction
"""

from pyteal import ABIReturnSubroutine, Assert, Expr, Global, Txn

from contracts_unified.core.state_handler.global_handler import GlobalStateHandler


@ABIReturnSubroutine
def sender_is_sig_validator() -> Expr:
    """Validates the sender is the  signature validator """

    return Assert(GlobalStateHandler.get_signature_validator() == Txn.sender())

def sender_is_creator():
    """Checks if the argument account is the creator of this contract"""

    return Assert(Global.creator_address() == Txn.sender())
