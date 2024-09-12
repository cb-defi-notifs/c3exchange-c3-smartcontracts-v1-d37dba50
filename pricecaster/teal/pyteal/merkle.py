"""
===============================================================================================

The Pricecaster Onchain Program

Version 10.0

(c) 2022-23 C3  LLC

Merkle Proof Verification Code

===============================================================================================
"""

from pyteal import *

MERKLE_HASH_SIZE = Int(20)
LEAF_PREFIX = Bytes("base16", "0x00")
NODE_PREFIX = Bytes("base16", "0x01")

def Keccak160(v):
    """
    Implements the truncated Keccak-256 hash function to 20 bytes needed by the merkle tree.
    """
    return Extract(Keccak256(v), Int(0), MERKLE_HASH_SIZE)


def HashData(data):
    """
    Implements the hash function for a merkle tree leaf.
    """
    return Keccak160(Concat(LEAF_PREFIX, data))


def HashNode(n1, n2):
    """
    Implements the hash function for a merkle tree node.
    """
    tmp = ScratchVar(TealType.bytes)
    return Seq(
        If(BytesGt(n1, n2)).Then(
            tmp.store(Concat(n2, n1))
        ).Else(
            tmp.store(Concat(n1, n2))
        ),
        Keccak160(Concat(NODE_PREFIX, tmp.load()))
    )


@Subroutine(TealType.uint64)
def merkle_proof_verify(price_update_entry, merkle_path, merkle_path_node_count, merkle_root):
    """

    Verify a merkle proof for a price update entry by traversing the provided
    merkle path and comparing the resulting hash to the merkle root.

    :param price_update_entry: The price update entry to verify
    :param merkle_path: The merkle path to traverse
    :param merkle_path_node_count: The number of nodes in the merkle path
    :param merkle_root: The merkle root to compare against
    :return: Whether the merkle proof is valid

    """

    i = ScratchVar(TealType.uint64)
    current_digest = ScratchVar(TealType.bytes)
    
    return Seq(
        current_digest.store(HashData(price_update_entry)),
        For(i.store(Int(0)), 
            i.load() < merkle_path_node_count, 
            i.store(i.load() + Int(1))).Do(
                current_digest.store(HashNode(current_digest.load(),
                                              Extract(merkle_path, 
                                                      i.load() * MERKLE_HASH_SIZE, 
                                                      MERKLE_HASH_SIZE)))
            ),
        current_digest.load() == merkle_root
    )


