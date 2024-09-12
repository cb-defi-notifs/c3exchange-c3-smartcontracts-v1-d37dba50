"""Setup the required pre-method checks"""


from pyteal import (
    Expr,
    Global,
    InnerTxnBuilder,
    Int,
    Seq,
    Subroutine,
    TealType,
    Txn,
    TxnField,
    While,
    abi,
)

from contracts_unified.library.c3types import AppId


@Subroutine(TealType.none)
def setup(opup_amount: Expr) -> Expr:
    """Setup the required pre-method OpUp and state handlers"""

    target = AppId()
    i = abi.Uint64()

    return Seq(
        # Get target
        # FIXME: Use the price caster when we can
        target.set(Txn.applications[1]),

        # Loop over the opup request
        # NOTE: We can't use the PyTEAL op-up because of ABI issues
        i.set(opup_amount),
        While(i.get() >= Global.min_txn_fee()).Do(
            InnerTxnBuilder.ExecuteMethodCall(
                app_id=target.get(),
                method_signature="nop()void",
                args=[],
                extra_fields={TxnField.fee: Int(0)}
            ),
            i.set(i.get() - Global.min_txn_fee()),
        ),
    )
