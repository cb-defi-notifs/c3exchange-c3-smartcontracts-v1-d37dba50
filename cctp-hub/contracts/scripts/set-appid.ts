import { JsonRpcProvider } from "ethers"
import { bigIntToBytes } from "../test/common"
import hre from 'hardhat';
import { ReadLine, createInterface } from "readline";

const C3CCTPHub = require('../artifacts/contracts/C3-CCTP-Hub.sol/C3_CCTP_Hub.json')
const ethers = require('ethers')
    
const rl: ReadLine = createInterface({
    input: process.stdin,
    output: process.stdout
});


(async () => {
    if (!process.env.AUTH_C3_APPID) throw Error("AUTH_C3_APPID environment variable not set")
    if (!process.env.HUB_ADDRESS) throw Error("HUB_ADDRESS environment variable not set")
    if (!process.env.LEDGER_ACCOUNT) {
        throw Error("LEDGER_ACCOUNT environment variable not set")
    }
    const appId = process.env.AUTH_C3_APPID
    const hubAddress = process.env.HUB_ADDRESS
    const ledgerAccount = process.env.LEDGER_ACCOUNT
    const encodedAppId = `0x${Buffer.from(bigIntToBytes(BigInt(process.env.AUTH_C3_APPID!), 8)).toString('hex')}`


    console.log('\nC3 CCTP Hub  Deployment Utility')
    console.log('-----------------------------------------------------------------\n')

    console.log('Changing parameter of Hub Address ', hubAddress)
    console.log('AppId / Encoded                   ', appId, encodedAppId)
    console.log('Ledger account                    ', ledgerAccount)

    console.log('\nFor a successful execution please consider:')
    console.log('* Unlock your Ledger, open the Ethereum application and set BLIND SIGNING to Enabled')
    console.log('* Transfer enough AVAX to your Ledger account to cover the deployment cost')
    
    rl.question('\nDo you want to proceed? Type YES to continue or anything else to abort.', async (answer: string) => {
        if (answer === 'YES') {
            console.log('Proceeding with execution...');
            const ledgerSigner = await hre.ethers.getSigner(ledgerAccount)
            const hub = await hre.ethers.getContractAt('C3_CCTP_Hub', hubAddress, ledgerSigner)
            const tx = await hub.setAuthorizedC3AppId(encodedAppId)
        
            console.log('Please wait...')
            const receipt = await tx.wait()
        
            console.log ('Transaction receipt:', receipt)
            console.log('\nDone, bye.')
        } else {
            console.log('Aborted by user.')
            process.exit(-1);
        }
        rl.close();
    });
})()
