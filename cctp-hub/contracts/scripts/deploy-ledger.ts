import { bigIntToBytes } from "algosdk";
import { ethers } from "hardhat";
import hre from 'hardhat';
const whsdk = require('@certusone/wormhole-sdk');
import { ReadLine, createInterface } from "readline";

    
const rl: ReadLine = createInterface({
    input: process.stdin,
    output: process.stdout
});


async function main() {
    if (!process.env.LEDGER_ACCOUNT) throw Error("LEDGER_ACCOUNT environment variable not set")

    if (!process.env.AUTH_C3_APPID) throw Error("AUTH_C3_APPID environment variable not set")
    if (!(process.env.NETWORK === 'MAINNET' || process.env.NETWORK === 'TESTNET' || process.env.NETWORK === 'DEVNET'))
        throw Error("NETWORK environment variable must be either MAINNET, TESTNET, or DEVNET")

    const ENCODED_AUTH_C3_APPID = `0x${Buffer.from(bigIntToBytes(BigInt(process.env.AUTH_C3_APPID!), 8)).toString('hex')}`
    const TOKEN_BRIDGE = whsdk.CONTRACTS[process.env.NETWORK!].avalanche.token_bridge

    let CIRCLE_INTEGRATION = ''
    let CIRCLE_TOKEN_BRIDGE = ''

    if (process.env.NETWORK === 'MAINNET') {
        if (!process.env.AVALANCHE_MAINNET_INFURA_API_KEY) throw Error("AVALANCHE_MAINNET_INFURA_API_KEY environment variable not set")
        CIRCLE_INTEGRATION = '0x09Fb06A271faFf70A651047395AaEb6265265F13'
        CIRCLE_TOKEN_BRIDGE = '0x6b25532e1060ce10cc3b0a99e5683b91bfde6982'

    } else if (process.env.NETWORK === 'TESTNET') {
        if (!process.env.FUJI_INFURA_API_KEY) throw Error("FUJI_INFURA_API_KEY environment variable not set")
        CIRCLE_INTEGRATION = '0x58f4c17449c90665891c42e14d34aae7a26a472e'
        CIRCLE_TOKEN_BRIDGE = '0xeb08f243e5d3fcff26a9e38ae5520a669f4019d0'

    } else if (process.env.NETWORK === 'DEVNET') {
        CIRCLE_INTEGRATION = '0xffffffffffffffffffffffffffffffffffffffff'
        CIRCLE_TOKEN_BRIDGE = '0xffffffffffffffffffffffffffffffffffffffff'
    }

    if (!ethers.isAddress(CIRCLE_INTEGRATION))
        throw new Error("CIRCLE_INTEGRATION is not a valid address")

    if (!ethers.isAddress(CIRCLE_TOKEN_BRIDGE))
        throw new Error("CIRCLE_TOKEN_BRIDGE is not a valid address")

    console.log('\nC3 CCTP Hub  Deployment Utility')
    console.log('-----------------------------------------------------------------\n')

    console.log('Deploying C3 CCTP Hub to ' + process.env.NETWORK + ' with the following parameters:')
    console.log('CIRCLE_INTEGRATION           ', CIRCLE_INTEGRATION)
    console.log('TOKEN_BRIDGE                 ', TOKEN_BRIDGE)
    console.log('CIRCLE_TOKEN_BRIDGE          ', CIRCLE_TOKEN_BRIDGE)
    console.log('APPID, ENCODED_AUTH_C3_APPID ', process.env.AUTH_C3_APPID, ENCODED_AUTH_C3_APPID)
    console.log('Ledger account:', process.env.LEDGER_ACCOUNT!)

    console.log('\nFor a successful deployment please consider:')
    console.log('* Unlock your Ledger, open the Ethereum application and set BLIND SIGNING to Enabled')
    console.log('* Transfer enough AVAX to your Ledger account to cover the deployment cost')
    
    rl.question('\nDo you want to proceed? Type YES to continue or anything else to abort.', async (answer: string) => {
        if (answer === 'YES') {
            console.log('Proceeding with deployment...');
            await deploy(CIRCLE_INTEGRATION, TOKEN_BRIDGE, CIRCLE_TOKEN_BRIDGE, ENCODED_AUTH_C3_APPID, process.env.LEDGER_ACCOUNT!)
            console.log('\nDone, bye.')
        } else {
            console.log('Aborted by user.')
            process.exit(-1);
        }
        rl.close();
    });
}


async function deploy(circleIntegrationAddress: string, 
    tokenBridgeAddress: string, 
    circleBridgeAddress: string,
    encodedAuthC3AppId: string, 
    ledgerAccount: string) {
    const factory = await ethers.getContractFactory("C3_CCTP_Hub")
        const deployTx = await factory.getDeployTransaction(circleIntegrationAddress, tokenBridgeAddress, circleBridgeAddress, encodedAuthC3AppId)

        const rawSignature: string = await hre.network.provider.request({
            method: "personal_sign",
            params: [ethers.hexlify(deployTx.data), ledgerAccount],
        }) as string

        const signature = ethers.Signature.from(rawSignature)

        const signedTx = {
            data: deployTx.data,
            v: signature.v,
            r: signature.r,
            s: signature.s
        }

        const ledgerSigner = await hre.ethers.getSigner(ledgerAccount)
        const tx = await ledgerSigner.sendTransaction(signedTx)

        console.log('Ledger transaction hash:', tx.hash)

        const rcpt = await tx.wait()
        console.log('Transaction receipt: ', rcpt)
}

// We recommend this pattern to be able to use async/await everywhere
// and properly handle errors.
main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
