"""General math functions"""

from pyteal import (
    ABIReturnSubroutine,
    Expr,
    If,
    Int,
    Seq,
    Subroutine,
    TealType,
    While,
    WideRatio,
    abi,
)

from contracts_unified.library.c3types import InterestRate
from contracts_unified.library.constants import RATE_ONE


@Subroutine(TealType.uint64)
def unsigned_min(lhs: Expr, rhs: Expr) -> Expr:
    """Returns the minimum of two values"""
    return If(lhs < rhs, lhs, rhs)


@Subroutine(TealType.uint64)
def unsigned_max(lhs: Expr, rhs: Expr) -> Expr:
    """Returns the maximum of two values"""
    return If(lhs > rhs, lhs, rhs)


@ABIReturnSubroutine
def teal_expt(
    base: InterestRate,
    raised_to: abi.Uint64,
    *,
    output: InterestRate,
) -> Expr:
    """Calculates base ** n"""

    power = abi.Uint64()

    return Seq(
        power.set(base),
        output.set(Int(RATE_ONE)),

        While(raised_to.get() > Int(0)).Do(
            If(raised_to.get() & Int(1))
            .Then(output.set(WideRatio([output.get(), power.get()], [Int(RATE_ONE)]))),
            power.set(WideRatio([power.get(), power.get()], [Int(RATE_ONE)])),
            raised_to.set(raised_to.get() >> Int(1)),
        )
    )
