// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;
import "solidity-bytes-utils/contracts/BytesLib.sol";

using BytesLib for bytes;
struct TransferWithPayload {
    // PayloadID uint8 = 3
    uint8 payloadID;
    // Amount being transferred (big-endian uint256)
    uint256 amount;
    // Address of the token. Left-zero-padded if shorter than 32 bytes
    bytes32 tokenAddress;
    // Chain ID of the token
    uint16 tokenChain;
    // Address of the recipient. Left-zero-padded if shorter than 32 bytes
    bytes32 to;
    // Chain ID of the recipient
    uint16 toChain;
    // Address of the message sender. Left-zero-padded if shorter than 32 bytes
    bytes32 fromAddress;
    // An arbitrary payload
    bytes payload;
}

struct Signature {
    bytes32 r;
    bytes32 s;
    uint8 v;
    uint8 guardianIndex;
}

struct VM {
    uint8 version;
    uint32 timestamp;
    uint32 nonce;
    uint16 emitterChainId;
    bytes32 emitterAddress;
    uint64 sequence;
    uint8 consistencyLevel;
    bytes payload;
    uint32 guardianSetIndex;
    Signature[] signatures;
    bytes32 hash;
}

contract MockTokenBridge {
    uint64 private _seq;

    function transferTokensWithPayload(
        address,
        uint256,
        uint16,
        bytes32,
        uint32,
        bytes memory
    ) external payable returns (uint64 sequence) {
        sequence = _seq + 1;
    }

    /*
     * @dev Parse a token transfer with payload (payload id 3).
     *
     * @params encoded The byte array corresponding to the token transfer (not
     *                 the whole VAA, only the payload)
     */
    function parseTransferWithPayload(
        bytes memory encoded
    ) public pure returns (TransferWithPayload memory transfer) {
        uint index = 0;

        transfer.payloadID = encoded.toUint8(index);
        index += 1;

        require(transfer.payloadID == 3, "invalid Transfer");

        transfer.amount = encoded.toUint256(index);
        index += 32;

        transfer.tokenAddress = encoded.toBytes32(index);
        index += 32;

        transfer.tokenChain = encoded.toUint16(index);
        index += 2;

        transfer.to = encoded.toBytes32(index);
        index += 32;

        transfer.toChain = encoded.toUint16(index);
        index += 2;

        transfer.fromAddress = encoded.toBytes32(index);
        index += 32;

        transfer.payload = encoded.slice(index, encoded.length - index);
    }

    /**
     * @dev parseVM serves to parse an encodedVM into a vm struct
     *  - it intentionally performs no validation functions, it simply parses raw into a struct
     */
    function parseVM(
        bytes memory encodedVM
    ) public pure virtual returns (VM memory vm) {
        uint index = 0;

        vm.version = encodedVM.toUint8(index);
        index += 1;
        // SECURITY: Note that currently the VM.version is not part of the hash
        // and for reasons described below it cannot be made part of the hash.
        // This means that this field's integrity is not protected and cannot be trusted.
        // This is not a problem today since there is only one accepted version, but it
        // could be a problem if we wanted to allow other versions in the future.
        require(vm.version == 1, "VM version incompatible");

        vm.guardianSetIndex = encodedVM.toUint32(index);
        index += 4;

        // Parse Signatures
        uint256 signersLen = encodedVM.toUint8(index);
        index += 1;
        vm.signatures = new Signature[](signersLen);
        for (uint i = 0; i < signersLen; i++) {
            vm.signatures[i].guardianIndex = encodedVM.toUint8(index);
            index += 1;

            vm.signatures[i].r = encodedVM.toBytes32(index);
            index += 32;
            vm.signatures[i].s = encodedVM.toBytes32(index);
            index += 32;
            vm.signatures[i].v = encodedVM.toUint8(index) + 27;
            index += 1;
        }

        /*
        Hash the body

        SECURITY: Do not change the way the hash of a VM is computed! 
        Changing it could result into two different hashes for the same observation. 
        But xDapps rely on the hash of an observation for replay protection.
        */
        bytes memory body = encodedVM.slice(index, encodedVM.length - index);
        vm.hash = keccak256(abi.encodePacked(keccak256(body)));

        // Parse the body
        vm.timestamp = encodedVM.toUint32(index);
        index += 4;

        vm.nonce = encodedVM.toUint32(index);
        index += 4;

        vm.emitterChainId = encodedVM.toUint16(index);
        index += 2;

        vm.emitterAddress = encodedVM.toBytes32(index);
        index += 32;

        vm.sequence = encodedVM.toUint64(index);
        index += 8;

        vm.consistencyLevel = encodedVM.toUint8(index);
        index += 1;

        vm.payload = encodedVM.slice(index, encodedVM.length - index);
    }

    function completeTransferWithPayload(
        bytes memory encodedVm
    ) external pure returns (bytes memory) {
        return parseVM(encodedVm).payload;
    }
}
