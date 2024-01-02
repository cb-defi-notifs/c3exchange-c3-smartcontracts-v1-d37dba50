// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;

import "../interfaces/ICircleIntegration.sol";
import "solidity-bytes-utils/contracts/BytesLib.sol";

using BytesLib for bytes;

/**
 * @notice `decodeDepositWithPayload` decodes an encoded `DepositWithPayload` struct
 * @dev reverts if:
 * - the first byte (payloadId) does not equal 1
 * - the length of the payload is short or longer than expected
 * @param encoded Encoded `DepositWithPayload` struct
 * @return message `DepositWithPayload` struct containing the following attributes:
 * - `token` Address (bytes32 left-zero-padded) of token to be minted
 * - `amount` Amount of tokens to be minted
 * - `sourceDomain` Circle domain for the source chain
 * - `targetDomain` Circle domain for the target chain
 * - `nonce` Circle sequence number for the transfer
 * - `fromAddress` Source CircleIntegration contract caller's address
 * - `mintRecipient` Recipient of minted tokens (must be caller of this contract)
 * - `payload` Arbitrary Wormhole message payload
 */
function decodeDepositWithPayload(bytes memory encoded) pure returns (ICircleIntegration.DepositWithPayload memory message) {
    // payloadId
    require(encoded.toUint8(0) == 1, "invalid message payloadId");

    uint256 index = 1;

    // token address
    message.token = encoded.toBytes32(index);
    index += 32;

    // token amount
    message.amount = encoded.toUint256(index);
    index += 32;

    // source domain
    message.sourceDomain = encoded.toUint32(index);
    index += 4;  

    // target domain
    message.targetDomain = encoded.toUint32(index);
    index += 4;

    // nonce
    message.nonce = encoded.toUint64(index);
    index += 8;

    // fromAddress (contract caller)
    message.fromAddress = encoded.toBytes32(index);
    index += 32;

    // mintRecipient (target contract)
    message.mintRecipient = encoded.toBytes32(index);
    index += 32;

    // message payload length
    uint256 payloadLen = encoded.toUint16(index);
    index += 2;

    // parse the additional payload to confirm the entire message was parsed
    message.payload = encoded.slice(index, payloadLen);
    index += payloadLen;

    // confirm that the message payload is the expected length
    require(index == encoded.length, "invalid message length");
}

//
// //   struct DepositWithPayload {
//         bytes32 token;
//         uint256 amount;
//         uint32 sourceDomain;
//         uint32 targetDomain;
//         uint64 nonce;
//         bytes32 fromAddress;
//         bytes32 mintRecipient;
//         bytes payload;
//     }
contract MockCircleIntegration {
    function redeemTokensWithPayload(ICircleIntegration.RedeemParameters memory params)
        external
        pure
        returns (ICircleIntegration.DepositWithPayload memory depositWithPayload)
        {
            depositWithPayload = decodeDepositWithPayload(params.encodedWormholeMessage);                   
        }

    function getDomainFromChainId(uint16) external pure returns (uint32) {
        return 0; // Always return Ethereum
    }

}