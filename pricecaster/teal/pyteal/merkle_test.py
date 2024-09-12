
# Testing functions for Merkle-tree verification.
#
# Use for reference.

from ast import For
from pyteal import Bytes, Concat, Extract, Int, ScratchVar, Seq, TealType
from merkle import HashData, HashNode, Keccak160, LEAF_PREFIX, MERKLE_HASH_SIZE, NODE_PREFIX

def test_merkle_proof_verify():
    i = ScratchVar(TealType.uint64)
    h1 = ScratchVar(TealType.bytes)
    h2 = ScratchVar(TealType.bytes)
    h3 = ScratchVar(TealType.bytes)
    h4 = ScratchVar(TealType.bytes)
    h5 = ScratchVar(TealType.bytes)
    h6 = ScratchVar(TealType.bytes)
    h7 = ScratchVar(TealType.bytes)
    htree = ScratchVar(TealType.bytes)
    current_digest = ScratchVar(TealType.bytes)
    return Seq(
        h1.store(HashData(Bytes("base16", "adad11"))),
        h2.store(HashData(Bytes("base16", "adad12"))),
        h3.store(HashData(Bytes("base16", "adad13"))),
        h4.store(HashData(Bytes("base16", "adad14"))),
        h5.store(HashNode(h1.load(), h2.load())),
        h6.store(HashNode(h3.load(), h4.load())),
        h7.store(HashNode(h5.load(), h6.load())),
        htree.store(Concat(h1.load(), h2.load(), h3.load(), h4.load(), h5.load(), h6.load(), h7.load())),

        current_digest.store(HashData(Bytes("base16", "adad11"))),
        For(i.store(Int(0)), i.load() < Int(2), i.store(i.load() + Int(1))).Do(
            Seq(
                current_digest.store(HashNode(current_digest.load(),
                                              Extract(Concat(h2.load(), h6.load()), i.load() * MERKLE_HASH_SIZE, MERKLE_HASH_SIZE)))
            )
        ),
        current_digest.load() == h7.load(),
    )


def test_hash_data():
    """
    Test the hash function for a merkle tree leaf
    """
    data = Bytes("base16", "00640000000000000000000000000000000000000000000000000000000000000000000000000000640000000000000064000000640000000000000064000000000000006400000000000000640000000000000064")

    return Seq(
        Keccak160(Concat(LEAF_PREFIX, data)) == Bytes("base16", "afc6a8ac466430f35895055f8a4c951785dad5ce"),
    )


def test_hash_node():
    """
    Test the hash function for a merkle tree node.
    """
    h1 = Bytes("base16", "05c51b04b820c0f704e3fdd2e4fc1e70aff26dff")
    h2 = Bytes("base16", "1e108841c8d21c7a5c4860c8c3499c918ea9e0ac")

    return Seq(
        HashNode(h1, h2) == Bytes("base16", "2d0e4fde68184c7ce8af426a0865bd41ef84dfa4"),
    )



