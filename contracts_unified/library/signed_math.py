"""Signed math functions"""

from pyteal import (
    Assert,
    Expr,
    If,
    Int,
    MultiValue,
    Not,
    Op,
    Or,
    Seq,
    Subroutine,
    TealType,
    abi,
)

# TODO: Use ABI types

def signed_ltz(value: Expr) -> Expr:
    """Signed less than zero"""
    return value & Int(0x8000000000000000)

@Subroutine(TealType.uint64)
def signed_neg(value: Expr) -> Expr:
    """Signed negation"""
    # Special case for zero because of wrap around
    return If(Not(value), value, ~value + Int(1))

@Subroutine(TealType.uint64)
def signed_abs(value: Expr) -> Expr:
    """Absolute value of a signed number"""
    return If(signed_ltz(value), signed_neg(value), value)

# TODO: Remove this and use addw when it's in pyteal
@Subroutine(TealType.uint64)
def signed_add(lhs: Expr, rhs: Expr) -> Expr:
    """Signed addition"""
    add_result = MultiValue(
        Op.addw,
        [TealType.uint64, TealType.uint64],
        args=[lhs, rhs],
        # TODO: add compile check to check version
    )

    return Seq(
        # Find sum
        add_result,
        (signed := abi.Uint64()).set(signed_ltz(lhs)),
        # Detect overflow when both inputs have the same sign and the result has a different sign
        Assert(
            Or(
                signed.get() != signed_ltz(rhs),
                signed.get() == signed_ltz(add_result.output_slots[1].load()),
            )
        ),
        add_result.output_slots[1].load(),
    )

@Subroutine(TealType.uint64)
def signed_sub(lhs: Expr, rhs: Expr) -> Expr:
    """Signed subtraction"""
    return signed_add(lhs, signed_neg(rhs))


@Subroutine(TealType.uint64)
def signed_gte(lhs: Expr, rhs: Expr) -> Expr:
    """Signed greater than or equal to"""
    return Seq(
        If(signed_ltz(lhs))
        .Then(If(signed_ltz(rhs), lhs >= rhs, Int(0)))
        .Else(If(signed_ltz(rhs), Int(1), lhs >= rhs))
    )


@Subroutine(TealType.uint64)
def signed_min(lhs: Expr, rhs: Expr) -> Expr:
    """Returns the minimum of two signed values"""
    return If(signed_gte(lhs,rhs), rhs, lhs)


@Subroutine(TealType.uint64)
def signed_max(lhs: Expr, rhs: Expr) -> Expr:
    """Returns the maximum of two signed values"""
    return If(signed_gte(lhs,rhs), lhs, rhs)
