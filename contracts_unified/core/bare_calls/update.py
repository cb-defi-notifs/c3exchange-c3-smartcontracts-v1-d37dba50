"""
Implements Core contract update ABI bare call.
"""

from pyteal import Expr, Subroutine, TealType

from contracts_unified.core.internal.validate_sender import sender_is_creator


@Subroutine(TealType.none)
def update() -> Expr:
    """Implements the contract method called on update"""

    return sender_is_creator()

@Subroutine(TealType.none)
def delete() -> Expr:
    """Implements the contract method called on delete"""

    return sender_is_creator()
