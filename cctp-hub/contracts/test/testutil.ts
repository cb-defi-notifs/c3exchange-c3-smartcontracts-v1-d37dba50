import { encodeUint8, encodeUint32, encodeUint16, CONTRACTS, CHAIN_ID_ALGORAND, CHAIN_ID_AVAX } from "@c3exchange/common"
import { MockGuardians, MockTokenBridge } from "@certusone/wormhole-sdk/lib/cjs/mock"
import { encodeUint64, bigIntToBytes } from "algosdk"
import { config, ethers } from "hardhat"

export function generateDepositPayload(
    payloadId: number,
    token: string,
    amount: number,
    sourceDomain: number,
    targetDomain: number,
    nonce: number,
    fromAddress: string,
    mintRecipient: string,
    sourceChain: number,
    sender: string,
    c3AppId: number | bigint,
    c3payloadAddendum?: Buffer,
    prefix: string = "wormholeDeposit"
  ) {
    const c3payload = Buffer.concat([
      Buffer.from(prefix),
      Buffer.from('f'.repeat(64), 'hex'),
      Buffer.from(encodeUint64(0)),
      Buffer.from(encodeUint64(c3AppId)),
      Buffer.from(encodeUint16(sourceChain)), 
      Buffer.from(sender.slice(2).padStart(64, '0'), 'hex'), 
      c3payloadAddendum ?? Buffer.alloc(0)])
  
    const payloadLen = c3payload.length
  
    const data = Buffer.concat([
      Buffer.from(encodeUint8(payloadId)),
      Buffer.from(token.slice(2).padStart(64, '0'), 'hex'),
      Buffer.from(bigIntToBytes(amount, 32)),
      Buffer.from(encodeUint32(sourceDomain)),
      Buffer.from(encodeUint32(targetDomain)),
      Buffer.from(encodeUint64(nonce)),
      Buffer.from(fromAddress.slice(2).padStart(64, '0'), 'hex'),
      Buffer.from(mintRecipient.slice(2).padStart(64, '0'), 'hex'),
      Buffer.from(encodeUint16(payloadLen)),
      c3payload
      ])
  
    return { data, c3payload }
  }

export function generateWithdrawPayload(
  mintRecipient: string,
  chainId: number,
  MOCK_APP_ID: number | bigint,
  prefix: string = "cctpWithdraw"
) {
  return Buffer.concat([
    Buffer.from(prefix),
    Buffer.from(mintRecipient.slice(2).padStart(64, '0'), 'hex'),
    encodeUint16(chainId),
    bigIntToBytes(MOCK_APP_ID, 8)])
}

export function getSignedVaa(
  tokenAddress: string,
  amount: bigint,
  recipientChain: number,
  tokenChain: number,
  c3CctpHubAddress: string,
  c3withdrawPayload: Buffer,
  c3AppId: number | bigint,
) {
  const mockTokenBridge = new MockTokenBridge(
    Buffer.from(bigIntToBytes(BigInt(CONTRACTS['TESTNET'].algorand.token_bridge), 32)).toString('hex'),
    CHAIN_ID_ALGORAND,
    1)

  const msg = mockTokenBridge.publishTransferTokensWithPayload(
    tokenAddress.slice(2).padStart(64, '0'),
    tokenChain,
    amount,
    recipientChain,
    c3CctpHubAddress.slice(2).padStart(64, '0'),
    Buffer.from(bigIntToBytes(c3AppId, 32)),
    c3withdrawPayload)

  const accounts: any = config.networks.hardhat.accounts
  const wallet = ethers.Wallet.fromPhrase(accounts.mnemonic);

  const mockGuardian = new MockGuardians(0, [
    wallet.privateKey
  ])

  const signedVaa = mockGuardian.addSignatures(msg, [0])

  return signedVaa
}