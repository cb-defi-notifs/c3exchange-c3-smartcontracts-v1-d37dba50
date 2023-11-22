"""
Clean any expired orders from the order book
"""

from pyteal import ABIReturnSubroutine, Assert, Expr, Global, Seq, abi

from contracts_unified.core.state_handler.global_handler import GlobalStateHandler


@ABIReturnSubroutine
def fund_mbr(
    payment_txn: abi.PaymentTransaction,
) -> Expr:
    """Register payment in algos for the MBR fund of the contract

    Arguments:

    payment_txn: The payment transaction that will fund this contract"""

    return Seq(
        Assert(payment_txn.get().receiver() == Global.current_application_address()),
        GlobalStateHandler.add_mbr_fund(payment_txn.get().amount())
    )
