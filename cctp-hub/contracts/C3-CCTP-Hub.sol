// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;
import "./interfaces/ICircleIntegration.sol";
import "./interfaces/ITokenBridge.sol";
import "./interfaces/circle/ICircleBridge.sol";
import "./interfaces/circle/IUSDC.sol";
import "./interfaces/circle/IMessageTransmitter.sol";
import "hardhat/console.sol";
import "solidity-bytes-utils/contracts/BytesLib.sol";
using BytesLib for bytes;

/// @title The C3 CCTP Hub Contract.
/// @author Hernán Di Pietro <hernan@c3.io>
/// @notice This contract acts as the glue component between Algorand/C3 and the Circle bridge infrastucture to support
///         native USDC token exchange. It performs two main tasks:
///         - Handling Deposits to C3: Redeems (mints) tokens sent via the Wormhole Integration Contract, obtaining Avalanche native USDC, and
///           subsequently sending those tokens via the Wormhole Token Bridge, triggering a C3 standard deposit by the
///           offchain relayer.
///         - Handling withdrawals from C3: Redeems tokens sent from Algorand/C3 core contract via the Wormhole Token Bridge to this
///           contract, and burn those wrapped USDCs by issuing a Circle Bridge contract call.  This will generate a transaction
///           with a set of logs that can be subsequently examined for getting an attestation to finally perform the minting at the
///           final wallet destination.
///
///           Security considerations:
///
///           This contract is not still secure nor audited.  Our design principles state:
///
///           * Use deployment and upgrade mechanisms with a multisig wallet.
///           * Perform administrative operations with a multisig or hardened (hardware?) wallet.
///           * For a decentralized, open architecture, the token operations can be called from anywhere.
///           * All parameters must be validated: for example, targeted at specific C3 Core AppIds, non zero amounts or correct payload
///             formats.
///
contract C3_CCTP_Hub {
    event RedeemAndTriggerDepositReturn(bytes32 initialTxHash, uint64 sequence);
    event BurnForWithdraw(bytes8 sourceC3Core, uint64 circleNonce);

    uint16 private constant CHAIN_ID_ALGORAND = 8;

    ICircleIntegration private _iCircleIntegration;
    ITokenBridge private _iTokenBridge;
    ICircleBridge private _iCircleBridge;
    address private _deployer;
    bytes8 private _authorizedC3AppId;

    /// Constructs a new C3 CCTP Hub contract.
    /// @param iCircleIntegration The Circle Integration contract address for the network this contract is operating on.
    /// @param iTokenBridge The Wormhole Token Bridge contract address for the network this contract is operating on.
    /// @param iCircleBridge The Circle Bridge contract address for the network this contract is operating on.
    /// @param authorizedC3AppId The authorized C3 AppId to deposit/withdraw tokens from. This must be encoded with AlgoSDK encodeUInt64
    constructor(
        ICircleIntegration iCircleIntegration,
        ITokenBridge iTokenBridge,
        ICircleBridge iCircleBridge,
        bytes8 authorizedC3AppId
    ) {
        require(uint256(bytes32(authorizedC3AppId)) != 0, "zero C3 appId");

        require(
            address(iCircleIntegration) != address(0),
            "zero CircleIntegration addr"
        );
        require(address(iTokenBridge) != address(0), "zero TokenBridge addr");
        require(address(iCircleBridge) != address(0), "zero CircleBridge addr");

        _deployer = msg.sender;
        _iCircleIntegration = iCircleIntegration;
        _iTokenBridge = iTokenBridge;
        _iCircleBridge = iCircleBridge;
        _authorizedC3AppId = authorizedC3AppId;
    }

    /// @notice Perform the redeem process by: calling the Wormhole Circle Integration Contract 'RedeemTokensWithPayload' method,
    ///         and if successful, call the Wormhole Token Bridge transfer functions to initiate a "classic" deposit operation that
    ///         will be handled by the C3 offchain relayer as we know.
    ///         The target C3 Core AppId contained in the payload must agree with the authorized one.
    /// @param initialTxHash The TX Hash that corresponds to the transfer from the user wallet to the Wormhole Integration Contract.
    ///                      This is logged in this call to be used to track transaction flow for clients such as the C3 Relayer.
    /// @param redeemParameters The redeem parameters created in the Token transfer process.
    function redeemAndTriggerDeposit(
        bytes32 initialTxHash,
        ICircleIntegration.RedeemParameters memory redeemParameters
    ) external {
        // redeem our tokens.

        ICircleIntegration.DepositWithPayload
            memory depositInfo = _iCircleIntegration.redeemTokensWithPayload(
                redeemParameters
            );

        // check the payload now that we have the decoded info, validate and revert if
        // anything is wrong.

        validateC3DepositPayload(depositInfo.payload);

        // Approve the Token Bridge to transfer our freshly minted tokens.

        address usdcToken = address(uint160(uint256(depositInfo.token)));

        IERC20(usdcToken).approve(address(_iTokenBridge), depositInfo.amount);

        // go ...

        uint64 sequence = _iTokenBridge.transferTokensWithPayload(
            usdcToken,
            depositInfo.amount,
            CHAIN_ID_ALGORAND,
            bytes32(uint256(uint64(_authorizedC3AppId))),
            uint32(depositInfo.nonce),
            depositInfo.payload
        );

        // keep reference data in a log.

        emit RedeemAndTriggerDepositReturn(initialTxHash, sequence);
    }

    /// @notice Redeems a token transfer from the Wormhole bridge and burn those tokens to be subsequently minted in the
    ///         final destination by the offchain relayer.
    /// @param vaa The VAA created when C3 Withdraw operation was issued.
    /// @return nonce The nonce of the transaction.
    /// @dev The caller of this operation will be the authorized address for the minting operation in the final destination.
    function burnForWithdraw(bytes memory vaa) external returns (uint64 nonce) {
        
        // redeem our tokens here....

        ITokenBridge.TransferWithPayload memory rv = _iTokenBridge
            .parseTransferWithPayload(
                _iTokenBridge.completeTransferWithPayload(vaa)
            );

        // We only redeem tokens with proper attached payload, validate.
        (bytes32 mintRecipient, uint16 chainId) = validateC3WithdrawPayload(rv.payload);

        // approve burn...

        address usdcToken = address(uint160(uint256(rv.tokenAddress)));
        IERC20(usdcToken).approve(address(_iCircleBridge), rv.amount);

        nonce =
            _iCircleBridge.depositForBurn(
                rv.amount,
                _iCircleIntegration.getDomainFromChainId(chainId),
                mintRecipient,
                usdcToken
            );

        emit BurnForWithdraw(_authorizedC3AppId, nonce);
    }

    /// Validates a C3 Deposit payload.
    /// @param payload The C3-generated  Deposit payload  to validate.
    function validateC3DepositPayload(bytes memory payload) internal view {
        // payload must be 87 bytes long: 'wormholeDeposit' + receiver public key + repay amount + target C3 Core AppId

        require(
            payload.length == 15 + 32 + 8 + 8 + 2 + 32,
            "payload length invalid must be 97 bytes"
        );

        require(
            (payload[0] == "w" &&
                payload[1] == "o" &&
                payload[2] == "r" &&
                payload[3] == "m" &&
                payload[4] == "h" &&
                payload[5] == "o" &&
                payload[6] == "l" &&
                payload[7] == "e" &&
                payload[8] == "D" &&
                payload[9] == "e" &&
                payload[10] == "p" &&
                payload[11] == "o" &&
                payload[12] == "s" &&
                payload[13] == "i" &&
                payload[14] == "t"),
            "payload header must be 'wormholeDeposit'"
        );

        require(
            payload[55] == _authorizedC3AppId[0] &&
                payload[56] == _authorizedC3AppId[1] &&
                payload[57] == _authorizedC3AppId[2] &&
                payload[58] == _authorizedC3AppId[3] &&
                payload[59] == _authorizedC3AppId[4] &&
                payload[60] == _authorizedC3AppId[5] &&
                payload[61] == _authorizedC3AppId[6] &&
                payload[62] == _authorizedC3AppId[7],
            "payload target C3 Core AppId must be authorized"
        );
    }

    /// Validates a C3 Withdraw payload.
    /// @param payload The C3-generated Withdraw payload to validate.
    function validateC3WithdrawPayload(bytes memory payload) internal view returns (
        bytes32 mintRecipient,
        uint16 chainId
    ) {
        // payload format: 'cctpWithdraw' + 32 byte dest address + 2 byte target ChainId + 8 byte target C3 Core AppId
        // expected length is : 12 + 32 + 2 + 8 = 54 bytes

        require(
            payload.length == 12 + 32 + 2 + 8,
            "payload length invalid must be 54 bytes"
        );

        require(
            (payload[0] == "c" &&
                payload[1] == "c" &&
                payload[2] == "t" &&
                payload[3] == "p" &&
                payload[4] == "W" &&
                payload[5] == "i" &&
                payload[6] == "t" &&
                payload[7] == "h" &&
                payload[8] == "d" &&
                payload[9] == "r" &&
                payload[10] == "a" &&
                payload[11] == "w"),
            "payload header must be 'cctpWithdraw'"
        );

        mintRecipient = payload.toBytes32(12);
        chainId = payload.toUint16(44);

        require(_authorizedC3AppId[7] == payload[53] && 
                _authorizedC3AppId[6] == payload[52] && 
                _authorizedC3AppId[5] == payload[51] && 
                _authorizedC3AppId[4] == payload[50] && 
                _authorizedC3AppId[3] == payload[49] && 
                _authorizedC3AppId[2] == payload[48] && 
                _authorizedC3AppId[1] == payload[47] && 
                _authorizedC3AppId[0] == payload[46], "payload source C3 Core AppId must be authorized");
    }

    // ---------------------- Accessors ------------------------------------------------

    /// @notice Returns the registered Circle Integration contract address for this contract.
    /// @return The Circle Integration contract address.
    function getCircleIntegrationAddress() external view returns (address) {
        return address(_iCircleIntegration);
    }

    /// @notice Returns the Wormhole Token Bridge contract address for this contract.
    /// @return The Wormhole Token Bridge contract address.
    function getTokenBridgeAddress() external view returns (address) {
        return address(_iTokenBridge);
    }

    /// @notice Returns the Circle Bridge contract address for this contract.
    /// @return The Circle Bridge contract address.
    function getCircleBridgeAddress() external view returns (address) {
        return address(_iCircleBridge);
    }

    /// @notice Returns the authorized C3 Core AppId for this contract.
    /// @return The authorized C3 Core AppId.
    function getAuthorizedC3AppId() external view returns (bytes8) {
        return _authorizedC3AppId;
    }

    function setAuthorizedC3AppId(bytes8 appId) external onlyDeployer {
        _authorizedC3AppId = appId;
    }

    // --------------------- Function modifiers ----------------------------------------

    modifier onlyDeployer() {
        require(_deployer == msg.sender, "only deployer is authorized");
        _;
    }
}
