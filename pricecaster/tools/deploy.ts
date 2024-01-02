/**
 *
 * Pricecaster V2 Deployment Tool.
 *
 * Copyright 2022 C3 LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

/* eslint-disable linebreak-style */

import algosdk from 'algosdk'
import { PricecasterLib, PRICECASTER_CI } from '@c3exchange/common'
const { exit } = require('process')
const readline = require('readline')
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
})
const spawnSync = require('child_process').spawnSync
const fs = require('fs')
const config = require('./deploy.config')
const PYTHON_BIN = 'python3.10'

function ask (questionText: string) {
  return new Promise((resolve) => {
    rl.question(questionText, (input: unknown) => resolve(input))
  })
}

let globalMnemo = ''

function signCallback (sender: string, tx: algosdk.Transaction) {
  return tx.signTxn(algosdk.mnemonicToSecretKey(globalMnemo).sk)
}

async function startOp (algodClient: algosdk.Algodv2, fromAddress: string, coreId: string, testModeEnable: boolean) {
  const pclib = new PricecasterLib(algodClient)

  const out = spawnSync(PYTHON_BIN, [config.sources.pricecaster_pyteal])
  if (out.error) {
    throw out.error
  }

  if (out.status !== 0) {
    throw out.stderr
  }

  console.log(out.output.toString())

  console.log('Deploying Pricecaster V2 Application...')
  const txId = await pclib.createPricecasterApp(fromAddress, fromAddress, fromAddress, parseInt(coreId), testModeEnable, testModeEnable, signCallback, 3000)
  console.log('txId: ' + txId)
  const txResponse = await pclib.waitForTransactionResponse(txId)
  const pkAppId = pclib.appIdFromCreateAppResponse(txResponse)
  console.log('Deployment App Id: %d', pkAppId)
  pclib.setAppId(PRICECASTER_CI, pkAppId)

  const dt = Date.now().toString()
  const resultsFileName = 'DEPLOY-' + dt

  console.log(`Writing deployment results file ${resultsFileName}...`)
  fs.writeFileSync(resultsFileName, `wormholeCoreAppId: ${coreId}\npricecasterAppId: ${pkAppId}\n`)
}

(async () => {
  console.log('\nPricecaster    Version 10.0  Algorand Application Deployment Tool')
  console.log('Copyright 2022, 23, 24 C3.io\n')

  if (process.argv.length !== 6) {
    console.log('Usage: deploy <coreid> <network> <keyfile>\n')
    console.log('where:\n')
    console.log('coreid                 The application id of the Wormhole core contract')
    console.log('network                Testnet, betanet, mainnet or dev (look in deploy.config.ts)')
    console.log('keyfile                Secret file containing deployer signing key mnemonic')
    console.log('testmode               Deploy test-mode contract to skip VAA/security checks')
    exit(0)
  }

  const coreId = process.argv[2]
  const network: string = process.argv[3]
  const keyfile: string = process.argv[4]
  const testmode: string = process.argv[5]

  const netconfig = config.networks[network]
  if (config === undefined) {
    console.log('Unsupported network: ' + network)
    exit(1)
  }

  try {
    globalMnemo = fs.readFileSync(keyfile).toString().trim()
    const algodClient = new algosdk.Algodv2(netconfig.token, netconfig.api, netconfig.port)
    const fromAddress = algosdk.mnemonicToSecretKey(globalMnemo).addr
    const testModeEnable = Number(testmode) > 0

    console.log('Parameters for deployment: ')
    console.log('From: ' + fromAddress)
    console.log('Network: ' + network)
    console.log('Wormhole Core AppId: ' + coreId)
    console.log('Testmode: ' + testModeEnable)
    const answer = await ask('\nEnter YES to confirm parameters, anything else to abort. ')
    if (answer !== 'YES') {
      console.warn('Aborted by user.')
      exit(1)
    }
    await startOp(algodClient, fromAddress, coreId, testModeEnable)
  } catch (e: any) {
    console.error('(!) Deployment Failed: ' + e.toString())
  }
  console.log('Bye.')
  exit(0)
})()
