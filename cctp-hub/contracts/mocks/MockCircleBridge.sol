// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;

contract MockCircleBridge {
    function depositForBurn(
        uint256,
        uint32,
        bytes32,
        address
    ) external pure returns (uint64 _nonce) {
        return 0;
    }
}