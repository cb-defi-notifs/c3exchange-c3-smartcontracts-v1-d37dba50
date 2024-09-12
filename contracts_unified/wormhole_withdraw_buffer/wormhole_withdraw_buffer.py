#
# Wormhole Withdraw Buffer Account
#
# This logicsig contract account works as a temporary man-in-the-middle buffer
# to perform withdrawals from C3 to foreign chains through Wormhole network,
# using the Wormhole SDK as the main transaction builder.
#
# (c) 2022, 2023 C3.io
# -------------------------------------------------------------------------
#

import sys

import click
from pyteal import (
    And,
    Approve,
    Assert,
    Bytes,
    Global,
    Gtxn,
    If,
    Int,
    Mode,
    OnComplete,
    OptimizeOptions,
    Seq,
    Tmpl,
    Txn,
    TxnType,
    abi,
    compileTeal,
)

# Assumed TX group structure for withdraws is :
#
# (* = optional transactions)
#  w = created by Wormhole SDK
#  c = created by C3
#
#
# tx#      kind
# w  *       Pay 1.02K (fund optin)
# w  *       Optin (dynmem stateless to Core)
# -------------------------------------------------------------------------
# c          UserProxy funding (~0.027 ALGO)
# c          Withdraw call to CE                   [txn_proxyrequest]
#            |
#            +--- inner call axfer CE to Withdraw buffer
# c          Withdraw buffer funding (fee 2000)
#
# w N-3      nop
# w N-2      Axfer from Withdraw buffer to Bridge
# w N-1      Sendtransfer call                    [txn_sendtransfer]
# -------------------------------------------------------------------------
#
# Assumed TX Group for asset addition:
#
# FundOptinTx
# Optin
# Fee
# "add_asset" call
#
# --------------------------------------------------------------------------


WITHDRAW_ABI_SELECTOR = Bytes("base16", "0x0dfac2ed")


SEND_TRANSFER_TXN_OFFSET_FROM_END = Int(1)
PROXY_REQUEST_TXN_OFFSET_FROM_END = Int(5)


class WithdrawBufferStaticData(abi.NamedTuple):
    """Static data for the user proxy contract"""
    # (address)
    token_bridge_id: abi.Field[abi.Uint64]
    server: abi.Field[abi.Address]  # 32 bytes


def wormhole_withdraw_buffer():
    txn_sendtransfer = Gtxn[Global.group_size() - SEND_TRANSFER_TXN_OFFSET_FROM_END]
    txn_fundoptin = Gtxn[Txn.group_index() - Int(1)]

    static_data = WithdrawBufferStaticData()

    return Seq(
        # Load static data
        static_data.decode(Tmpl.Bytes("TMPL_BN_STATIC_DATA")),

        # No re-keys or close outs!
        Assert(Txn.close_remainder_to() == Global.zero_address()),
        Assert(Txn.asset_close_to() == Global.zero_address()),
        Assert(Txn.rekey_to() == Global.zero_address()),
        Assert(Txn.fee() <= Int(2000)),

        # Allow asset optins for this staleless, funded by the server
        If(
            And(
                Txn.type_enum() == TxnType.AssetTransfer,
                Txn.asset_sender() == Global.zero_address(),
                Txn.sender() == Txn.asset_receiver(),
                Txn.asset_amount() == Int(0),
            )
        ).Then(
            Seq(
                Assert(txn_fundoptin.type_enum() == TxnType.Payment),
                static_data.server.use(lambda server: Assert(txn_fundoptin.sender() == server.get())),
                Approve(),
            )
        ),

        # NOTICE: Many transaction group properties are futher checked by
        # the Wormhole token bridge, see for reference:
        #
        # https://github.com/wormhole-foundation/wormhole/blob/248fd5a58807af9a679bcb994860286bd4dedef0/algorand/token_bridge.py#L686
        # Last transaction must be "Sendtransfer" call to Wormhole Token Bridge
        Assert(txn_sendtransfer.type_enum() == TxnType.ApplicationCall),
        Assert(txn_sendtransfer.on_completion() == OnComplete.NoOp),
        Assert(txn_sendtransfer.application_args[0] == Bytes("sendTransfer")),
        static_data.token_bridge_id.use(lambda token_bridge_id: Assert(txn_sendtransfer.application_id() == token_bridge_id.get())),

        Approve(),
    )


@click.command()
@click.argument("output_approval", type=click.File("w"))
def cli(output_approval):
    output_approval.write(
        compileTeal(
            wormhole_withdraw_buffer(),
            mode=Mode.Signature,
            assembleConstants=True,
            optimize=OptimizeOptions(scratch_slots=True),
            version=9,
        )
    )


if __name__ == "__main__":
    cli(sys.argv[1:])
