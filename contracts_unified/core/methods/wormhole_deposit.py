"""
Implements Core contract Wormhole-deposit ABI method.
"""


from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    Assert,
    Bytes,
    Expr,
    Global,
    Gtxn,
    Int,
    Seq,
    Txn,
    abi,
)

from contracts_unified.core.internal.setup import setup
from contracts_unified.core.methods.deposit import inner_deposit_asset
from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.library.c3types import (
    AccountAddress,
    Amount,
    DecodedWormholePayload,
    DepositWord,
    InstrumentId,
)
from contracts_unified.library.wormhole import decode_wormhole_payload
from contracts_unified.library.xassert import XAssert

# NOTE: The VAA does not come with the  ASA ID of the foreign token but with the
#       actual foreign token address which is useless from the PyTEAL code point of view, so
#       instead of scanning the group and the inner payment TXs (completeTransfer children),
#       looking for the asset Id we simply pass it as argument. Less error prone,
#       and we save a few bits of bytecode ;)

@ABIReturnSubroutine
def wormhole_deposit(
    portal_transfer_txn: abi.ApplicationCallTransaction,
    account: AccountAddress,
    payload: DepositWord,
    instrument_id: InstrumentId,
    opup_budget: Amount,
) -> Expr:
    """Implements the contract method called during an ASA deposit via Wormhole.

    Arguments:

    portal_transfer_txn (ApplicationCallTransaction): The ABI "ApplicationCallTransaction" argument referencing the previous transaction to this call in the "Wormhole Deposit" group.  Must be of type "application call".
    account (AccountAddress): Target account address to deposit to.
    payload (DepositWord): Payload, must equal to "WormholeDeposit" string-literal.
    instrument_id (InstrumentId): Instrument to transfer.
    opup_budget (Amount): Additional computation budget to allocate to this transaction.

    ----------------------------------------------------------------------------------------------------------------------------------

    Security rationale:  The completeTransfer method of the Wormhole Token Bridge guarantees that:

    - The VAA was processed by the vaaVerify method of the Wormhole Core.
    - The VAA matches the completeTransfer arg.
    - The portal_transfer method exists in the group and has the proper target appId matching the Vaa.
    - The portal_transfer method has the correct sender  (the server in our case)

    If we can ensure that the completeTransfer method exists in the group and it's from
    the canonical Wormhole Token Bridge Appid, we can transitively check remaining properties
    for additional security.

    Additionally, the innertxn doing the transfer actually uses the VAA information which
    we ensure is correct for the three sources:  this method, the completeTransfer method and the
    vaaVerify method in the Core.

    ref: https://github.com/wormhole-foundation/wormhole/blob/5255e933d68629f0643207b0f9d3fa797af5cbf7/algorand/token_bridge.py#L466

    """

    vaa = portal_transfer_txn.get().application_args[1]
    complete_transfer_txn = Gtxn[portal_transfer_txn.get().group_index() - Int(1)]
    decoded_payload = DecodedWormholePayload()
    abi_vaa = abi.make(abi.DynamicBytes)
    abi_amount = abi.Uint64()
    abi_repay_amount = abi.Uint64()
    abi_receiver = abi.Address()

    return Seq(
        setup(opup_budget.get()),

        # Ensure there are no rogue transactions past the box-budget setup
        Assert(Global.group_size() == Txn.group_index() + Int(2), comment="Unknown transactions ahead detected"),

        # Ensure completeTransfer from canonical Wormhole Token Bridge exists.
        Assert(complete_transfer_txn.application_args[0] == Bytes("completeTransfer"), comment="expected completeTransfer  method call"),
        Assert(complete_transfer_txn.application_id() == GlobalStateHandler.get_wormhole_bridge_id(), comment="completeTransfer call appId unknown"),

        # In our current design, owner == creator, so this is valid.  What we should check?
        Assert(complete_transfer_txn.sender() == GlobalStateHandler.get_operator_address(), comment="completeTransfer call sender unknown"),

        # Ensure VAAs match
        abi_vaa.decode(vaa),

        # The completeTransfer code ensures his VAA equals portal_transfer VAA, we check here
        # if we match our VAA
        Assert(complete_transfer_txn.application_args[1] == abi_vaa.get(), comment="VAAs do not match"),

        # Decode the VAA
        decoded_payload.set(cast(abi.ReturnedValue, decode_wormhole_payload(abi_vaa))),
        abi_amount.set(decoded_payload.amount),
        abi_repay_amount.set(decoded_payload.repay_amount),
        abi_receiver.set(decoded_payload.receiver),

        # Validate the VAA, do we need more checks?
        XAssert(
           abi_receiver.get() == account.get(),
           comment="Receiving user address mismatch",
        ),

        # Perform deposit
        cast(Expr, inner_deposit_asset(account, payload, instrument_id, abi_amount, abi_repay_amount)),
    )
