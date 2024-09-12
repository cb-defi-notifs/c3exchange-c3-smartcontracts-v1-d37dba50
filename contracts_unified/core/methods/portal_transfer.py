"""
Implements Core contract portal_transfer ABI method.

See integration-techdoc.md in the docs for rationale and
how this works in the context for Wormhole transaction groups.
"""
from pyteal import ABIReturnSubroutine, Assert, Bytes, Expr, Int, Len, Seq, abi


@ABIReturnSubroutine
def portal_transfer(vaa: abi.DynamicBytes, *, output: abi.DynamicBytes) -> Expr:
    """

    Called at the end of a transfer from the portal to C3 and
    use as a "marker" and VAA source for the deposit operation.

    Decoding and validation of the VAA, along with sender check is performed
    in the deposit operation, where this txn is referenced.

    """

    return Seq(
        Assert(Len(vaa.get()) != Int(0), comment="Empty VAA"),
        # Anything works here, since wormhole requires some value
        output.set(Bytes("base16", "0x00")),
    )
