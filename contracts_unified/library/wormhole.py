"""
Wormhole-support utilities.
"""

from pyteal import (
    ABIReturnSubroutine,
    Btoi,
    Bytes,
    Expr,
    Extract,
    ExtractUint64,
    Int,
    Len,
    Seq,
    abi,
)

from contracts_unified.library.c3types import DecodedWormholePayload

# Wormhole VAA and Payload constants

VAA_PAYLOAD_SIGNATURE = "wormholeDeposit"
VAA_HEADER_LEN = 6
VAA_SIGNATURE_LEN = 66
VAA_BODY_LEN = 51
VAA_PAYLOAD_LEN = 133

# Extracts amount and asset Id from a Wormhole VAA payload
#
# A friendly reminder...  (with one signature)
#
# Offset
# 0        LL (length prefix added by Wormhole)
#          010000000001 (Header)
#          signatures >>>
#          00d8d94fb29a9c9a9b9cbdfa9f93313cc65edb13f67bfa01f82e5bbf6e5170f1ed655ee5f229f95eaba7780d65960ea92598075a7adfc924d0098987d32cf4c26c01
#          <<< end of signatures
#          6322210800000001000897839569ec6a24f286a48b805c9812d07501e90b0271d89a8c40f8c1a8cce2e5000000000000000120 (body)
#
# 125      03   (payload type)
#          0000000000000000000000000000000000000000000000000000000000023280   (Amount)
#          0000000000000000000000000000000000000000000000000000000000000000   (token addr)
#          0008  (source chain)
#          0000000000000000000000000000000000000000000000000000000000000359   (destination)
#          0008  (dest chain)
#          0000000000000000000000000000000000000000000000000000000000000000   (fee)
#
#          custom payload
#
# 125+133  776f726d686f6c654465706f736974   ( bytes: "wormholeDeposit" )
#          d03578b22fdde3d5fd747f406c9cf1a59294f6173ca3147f831213e3681376bc   (receiver address)
#          0000000000000000                                                   (reserved for repayment)
#          0000000000004444                                                     CCTP-xfer destination appId
#          0002000000000000000000000000994f19cb59a1781cb6d06370bc81f1ed637a4b52 CCTP-xfer origin user chain/address
#

@ABIReturnSubroutine
def decode_wormhole_payload(
    vaa: abi.DynamicBytes, *, output: DecodedWormholePayload
) -> Expr:
    """Decodes a payload from wormhole"""

    payload_offset = abi.Uint64()
    num_of_signatures = Btoi(Extract(vaa.get(), Int(5), Int(1)))
    amount = abi.Uint64()
    receiver = abi.Address()
    repay_amount = abi.Uint64()

    return Seq(
            # Skip num of signatures and remaining body
            payload_offset.set(
                Int(VAA_HEADER_LEN + VAA_BODY_LEN)
                + Int(VAA_SIGNATURE_LEN) * num_of_signatures
            ),

            amount.set(ExtractUint64(vaa.get(), payload_offset.get() + Int(25))),
            receiver.set(Extract( vaa.get(), payload_offset.get() + Int(VAA_PAYLOAD_LEN) + Len(Bytes(VAA_PAYLOAD_SIGNATURE)), Int(32))),
            repay_amount.set(ExtractUint64(vaa.get(), payload_offset.get() + Int(VAA_PAYLOAD_LEN) + Len(Bytes(VAA_PAYLOAD_SIGNATURE)) + Int(32))),

            output.set(amount, receiver, repay_amount)
    )
