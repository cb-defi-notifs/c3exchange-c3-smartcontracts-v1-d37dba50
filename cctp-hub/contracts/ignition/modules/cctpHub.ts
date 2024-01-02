import { MockTokenBridge } from "@certusone/wormhole-sdk/lib/cjs/mock";
import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";
import "@nomicfoundation/hardhat-ledger";
import { bigIntToBytes } from "algosdk";
import { ethers } from "hardhat";
const whsdk = require('@certusone/wormhole-sdk');

// See https://docs.wormhole.com/wormhole/reference/constants#cctp
//
// https://developers.circle.com/stablecoin/docs/cctp-protocol-contract
//

if (!process.env.AUTH_C3_APPID) throw Error("AUTH_C3_APPID environment variable not set")
if (!(process.env.NETWORK === 'MAINNET' || process.env.NETWORK === 'TESTNET' || process.env.NETWORK === 'DEVNET'))
    throw Error("NETWORK environment variable must be either MAINNET, TESTNET, or DEVNET")

const ENCODED_AUTH_C3_APPID = `0x${Buffer.from(bigIntToBytes(BigInt(process.env.AUTH_C3_APPID!), 8)).toString('hex')}`
const TOKEN_BRIDGE = whsdk.CONTRACTS[process.env.NETWORK!].avalanche.token_bridge

let CIRCLE_INTEGRATION = ''
let CIRCLE_TOKEN_BRIDGE = ''

if (process.env.NETWORK === 'MAINNET') {
    CIRCLE_INTEGRATION = '0x58f4c17449c90665891c42e14d34aae7a26a472e'
    CIRCLE_TOKEN_BRIDGE = '0xeb08f243e5d3fcff26a9e38ae5520a669f4019d0'

} else if (process.env.NETWORK === 'TESTNET') {
    CIRCLE_INTEGRATION = '0x58f4c17449c90665891c42e14d34aae7a26a472e'
    CIRCLE_TOKEN_BRIDGE = '0xeb08f243e5d3fcff26a9e38ae5520a669f4019d0'

} else if (process.env.NETWORK === 'DEVNET') {
    CIRCLE_INTEGRATION = '0x58f4c17449c90665891c42e14d34aae7a26a472e'
    CIRCLE_TOKEN_BRIDGE = '0xeb08f243e5d3fcff26a9e38ae5520a669f4019d0'
}

if (!ethers.isAddress(CIRCLE_INTEGRATION)) 
    throw new Error("CIRCLE_INTEGRATION is not a valid address")

// if (!ethers.isAddress(TOKEN_BRIDGE))
//     throw new Error("TOKEN_BRIDGE is not a valid address")

if (!ethers.isAddress(CIRCLE_TOKEN_BRIDGE))
    throw new Error("CIRCLE_TOKEN_BRIDGE is not a valid address")

export default buildModule("C3CctpHubModule",  (m) => {

    

    // fix for hardhat network deployments
    const mockTokenBridge = process.env.NETWORK === 'DEVNET' ? m.contract("MockTokenBridge") : undefined

    const cctpHub = m.contract("C3_CCTP_Hub", [
        CIRCLE_INTEGRATION,
        mockTokenBridge ? mockTokenBridge.id : TOKEN_BRIDGE,
        CIRCLE_TOKEN_BRIDGE,
        ENCODED_AUTH_C3_APPID]);

    return { cctpHub };
});

