import { CHAIN_ID_ALGORAND, CHAIN_ID_AVAX, CONTRACTS, encodeUint16, encodeUint64 } from "@c3exchange/common";
import { MockTokenBridge, MockGuardians } from "@certusone/wormhole-sdk/lib/cjs/mock";
import {
  loadFixture
} from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { expect } from "chai";
import { config, ethers } from "hardhat";
import { ICircleIntegration } from "../typechain-types";
import { generateDepositPayload, generateWithdrawPayload, getSignedVaa } from "./testutil";
import { bigIntToBytes } from "./common";
import { CHAIN_ID_ETH, hexToUint8Array, parseTokenTransferVaa } from "@certusone/wormhole-sdk";

const USDC_ASAID = 166458877

describe("C3CctpHub", function () {
  const MOCK_APP_ID = 100n
  const initialTxHash = '0xb25045ca689cd9ff79f813b84701fcc34014959548a67687655dbcb43c927587'

  let mockCircleIntegrationAddress: string, mockCircleBridgeAddress: string, mockTokenBridgeAddress: string, mockUSDCAddress: string

  async function deployHubFixture() {

    const mockCircleBridgeDeploy = await ethers.deployContract("MockCircleBridge")
    mockCircleBridgeAddress = await mockCircleBridgeDeploy.getAddress()

    const mockTokenBridgeDeploy = await ethers.deployContract("MockTokenBridge")
    mockTokenBridgeAddress = await mockTokenBridgeDeploy.getAddress()

    const mockCircleIntegrationDeploy = await ethers.deployContract("MockCircleIntegration")
    mockCircleIntegrationAddress = await mockCircleIntegrationDeploy.getAddress()

    const mockUSDCDeploy = await ethers.deployContract("MockUSDC", ['USDC', 'USDC', 1000000000]);
    mockUSDCAddress = await mockUSDCDeploy.getAddress()

    // deploy hub
    const [owner, otherAccount] = await ethers.getSigners();
    const c3CctpHub = await deployHub(MOCK_APP_ID, mockCircleIntegrationAddress, mockTokenBridgeAddress, mockCircleBridgeAddress)

    return { owner, otherAccount, c3CctpHub };
  }

  async function deployHub(appId: number | bigint, circleIntegrationAddress: string, tokenBridgeAddress: string, circleBridgeAddress: string) {
    const c = await ethers.getContractFactory("C3_CCTP_Hub");
    return await c.deploy(
      circleIntegrationAddress,
      tokenBridgeAddress,
      circleBridgeAddress,
      encodeUint64(appId)
    )
  }

  describe("Deployment", function () {

    it("Should deploy C3CctpHub with proper values", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);

      expect(await c3CctpHub.getCircleBridgeAddress()).to.equal(mockCircleBridgeAddress)
      expect(await c3CctpHub.getTokenBridgeAddress()).to.equal(mockTokenBridgeAddress)
      expect(await c3CctpHub.getCircleIntegrationAddress()).to.equal(mockCircleIntegrationAddress)
      expect(await c3CctpHub.getAuthorizedC3AppId()).to.equal(MOCK_APP_ID)

    })

    it("Should fail deploy if the appId is zero", async function () {
      await expect(deployHub(0, mockCircleIntegrationAddress, mockTokenBridgeAddress, mockCircleBridgeAddress)).to.be.revertedWith(
        "zero C3 appId"
      )
    })

    it("Should fail deploy if the circleIntegrationAddress is zero", async function () {
      await expect(deployHub(MOCK_APP_ID, ethers.ZeroAddress, mockTokenBridgeAddress, mockCircleBridgeAddress)).to.be.revertedWith(
        "zero CircleIntegration addr")
    })

    it("Should fail deploy if the tokenBridgeAddress is zero", async function () {
      await expect(deployHub(MOCK_APP_ID, mockCircleIntegrationAddress, ethers.ZeroAddress, mockCircleBridgeAddress)).to.be.revertedWith(
        "zero TokenBridge addr")
    })

    it("Should fail deploy if the circleBridgeAddress is zero", async function () {
      await expect(deployHub(MOCK_APP_ID, mockCircleIntegrationAddress, mockTokenBridgeAddress, ethers.ZeroAddress)).to.be.revertedWith(
        "zero CircleBridge addr")
    })

    it("Should set new appId from owner", async function () {
      const { c3CctpHub, owner } = await loadFixture(deployHubFixture);
      const newAppId = 200n
      await c3CctpHub.connect(owner).setAuthorizedC3AppId(encodeUint64(newAppId))
      expect(await c3CctpHub.getAuthorizedC3AppId()).to.equal(newAppId)
    })

    it("Should fail to set new appId from non-owner", async function () {
      const { c3CctpHub, otherAccount } = await loadFixture(deployHubFixture);
      const newAppId = 200n
      await expect(c3CctpHub.connect(otherAccount).setAuthorizedC3AppId(encodeUint64(newAppId))).to.be.revertedWith(
        "only deployer is authorized"
      )
    })

    it("Should Redeem (mint) and transfer tokens during a deposit", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);
      const fromAddress = (await ethers.getSigners())[2].address;
      const mintRecipient = await c3CctpHub.getAddress();

      const depositPayload = generateDepositPayload(
        1, // payloadId
        mockUSDCAddress,
        100000,
        0, // Ethereum
        1, // Avalanche
        1, // nonce
        fromAddress,
        mintRecipient,
        2,
        fromAddress,
        MOCK_APP_ID
      )

    
      const redeemParameters: ICircleIntegration.RedeemParametersStruct = {
        encodedWormholeMessage: depositPayload.data,
        circleBridgeMessage: "0x1234",
        circleAttestation: "0x1234",
      }

      await expect(c3CctpHub.redeemAndTriggerDeposit(hexToUint8Array(initialTxHash), redeemParameters))
        .to.emit(c3CctpHub, "RedeemAndTriggerDepositReturn")
        .withArgs(initialTxHash, 1)
    })

    it("Should fail to redeem if C3 payload has invalid length", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);
      const fromAddress = (await ethers.getSigners())[2].address;
      const mintRecipient = await c3CctpHub.getAddress();

      const depositPayload = generateDepositPayload(
        1, // payloadId
        mockUSDCAddress,
        100000,
        0, // Ethereum
        1, // Avalanche
        1, // nonce
        fromAddress,
        mintRecipient,
        2,
        fromAddress,
        MOCK_APP_ID,
        Buffer.from('xyz')
      )

      const redeemParameters: ICircleIntegration.RedeemParametersStruct = {
        encodedWormholeMessage: depositPayload.data,
        circleBridgeMessage: "0x1234",
        circleAttestation: "0x1234",
      }

      await expect(c3CctpHub.redeemAndTriggerDeposit(hexToUint8Array(initialTxHash), redeemParameters)).to.be.revertedWith(
        "payload length invalid must be 97 bytes"
      )
    })

    it("Should fail to redeem if C3 payload has invalid prefix", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);
      const fromAddress = (await ethers.getSigners())[2].address;
      const mintRecipient = await c3CctpHub.getAddress();

      const depositPayload = generateDepositPayload(
        1, // payloadId
        mockUSDCAddress,
        100000,
        0, // Ethereum
        1, // Avalanche
        1, // nonce
        fromAddress,
        mintRecipient,
        2,
        fromAddress,
        MOCK_APP_ID,
        undefined,
        "wozzzoleDeposit"
      )

      const redeemParameters: ICircleIntegration.RedeemParametersStruct = {
        encodedWormholeMessage: depositPayload.data,
        circleBridgeMessage: "0x1234",
        circleAttestation: "0x1234",
      }

      await expect(c3CctpHub.redeemAndTriggerDeposit(hexToUint8Array(initialTxHash), redeemParameters)).to.be.revertedWith(
        "payload header must be 'wormholeDeposit'"
      )
    })

    it("Should fail to redeem if C3 payload points to unauthorized appId", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);
      const fromAddress = (await ethers.getSigners())[2].address;
      const mintRecipient = await c3CctpHub.getAddress();

      const depositPayload = generateDepositPayload(
        1, // payloadId
        mockUSDCAddress,
        100000,
        0, // Ethereum
        1, // Avalanche
        1, // nonce
        fromAddress,
        mintRecipient,
        2,
        fromAddress,
        MOCK_APP_ID + 666n
      )

      const redeemParameters: ICircleIntegration.RedeemParametersStruct = {
        encodedWormholeMessage: depositPayload.data,
        circleBridgeMessage: "0x1234",
        circleAttestation: "0x1234",
      }

      await expect(c3CctpHub.redeemAndTriggerDeposit(hexToUint8Array(initialTxHash), redeemParameters)).to.be.revertedWith(
        "payload target C3 Core AppId must be authorized"
      )
    })

    it("Should succeed to call burnForWithdraw", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);

      const mintRecipient = (await ethers.getSigners())[3].address
      const c3withdrawPayload = generateWithdrawPayload(
        mintRecipient,
        CHAIN_ID_ETH,
        MOCK_APP_ID
      )

      const amount = 10000n

      const signedVaa = getSignedVaa(mockUSDCAddress, 
        amount, 
        CHAIN_ID_AVAX, 
        CHAIN_ID_ALGORAND, 
        await c3CctpHub.getAddress(), 
        c3withdrawPayload, 
        MOCK_APP_ID)

      await expect(c3CctpHub.burnForWithdraw(signedVaa))
      .to.emit(c3CctpHub, "BurnForWithdraw")
      .withArgs(
        MOCK_APP_ID, 0)
    })

    it("Should fail to call burnForWithdraw if payload has invalid header", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);

      const mintRecipient = (await ethers.getSigners())[3].address
      const c3withdrawPayload = generateWithdrawPayload(
        mintRecipient,
        CHAIN_ID_ETH,
        MOCK_APP_ID,
        'xxxxWithdraw'
      )
      const signedVaa = getSignedVaa(mockUSDCAddress, 
        10000n,
        CHAIN_ID_AVAX, 
        CHAIN_ID_ALGORAND, 
        await c3CctpHub.getAddress(), 
        c3withdrawPayload, 
        MOCK_APP_ID)

      await expect(c3CctpHub.burnForWithdraw(signedVaa)).to.be.revertedWith(
        "payload header must be 'cctpWithdraw'"
      )
    })

    it("Should fail to call burnForWithdraw if origin address is not authorized C3 AppId", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);

      const mintRecipient = (await ethers.getSigners())[3].address
      const c3withdrawPayload = generateWithdrawPayload(
        mintRecipient,
        CHAIN_ID_ETH,
        MOCK_APP_ID + 2n
      )
      const signedVaa = getSignedVaa(mockUSDCAddress, 
        10000n,
        CHAIN_ID_AVAX, 
        CHAIN_ID_ALGORAND, 
        await c3CctpHub.getAddress(), 
        c3withdrawPayload, 
        MOCK_APP_ID + 2n)

        await expect(c3CctpHub.burnForWithdraw(signedVaa)).to.be.revertedWith(
          "payload source C3 Core AppId must be authorized"
        )
    })

    it("Should fail to call burnForWithdraw if payload length != 54", async function () {
      const { c3CctpHub } = await loadFixture(deployHubFixture);

      const mintRecipient = (await ethers.getSigners())[3].address
      const c3withdrawPayload = generateWithdrawPayload(
        mintRecipient,
        CHAIN_ID_ETH,
        MOCK_APP_ID,
        'cctpWithdrawmmmmmmmmmmmmmmmmmmmmmmmmm'
      )
      const signedVaa = getSignedVaa(mockUSDCAddress, 
        10000n,
        CHAIN_ID_AVAX, 
        CHAIN_ID_ALGORAND, 
        await c3CctpHub.getAddress(), 
        c3withdrawPayload, 
        MOCK_APP_ID)

      await expect(c3CctpHub.burnForWithdraw(signedVaa)).to.be.revertedWith(
        "payload length invalid must be 54 bytes"
      )
    })
  })
})