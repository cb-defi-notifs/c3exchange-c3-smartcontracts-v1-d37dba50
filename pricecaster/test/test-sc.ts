/* eslint-disable no-unused-expressions */
import { PRICECASTER_CI, PriceSlotData, PricecasterLib } from '@c3exchange/common'
import algosdk, { Account, Transaction, generateAccount, makePaymentTxnWithSuggestedParams } from 'algosdk'
import { after, before, describe, it } from 'mocha'
const { expect } = require('chai')
const chai = require('chai')
const spawnSync = require('child_process').spawnSync
const testConfig = require('./test-config')
chai.use(require('chai-as-promised'))
chai.config.truncateThreshold = 0

// Data for 1 price update: BTC

const PRICE_UPDATE_1 = '504e41550100000000a00100000000010014d68f4f2c8cd0fa74dec566575cffb2ebd10b5bb47dd9fee2685d6dd2dcf8191c40fedee580104918a12197830c58cbeda3f2b7087d6e41ffc2ce8cc6f1945b006537f36400000000001ae101faedac5851e32b9b23b5f9411a8c2bac4aae3ed4dd7b811dd1a72ea4aa710000000001f4947d014155575600000000000657321200002710395b432f2ca397535577362552b290a98c25eb9f0100550008f781a893bc9340140c5f89c8a96f438bcfae4d1474cc0f688e3a52892c731800000000009707110000000000000e28fffffff8000000006537ef40000000006537ef3e0000000000973516000000000000147f0a59298821406ca1058371d8140770f3e5e4f7793d229352c0ddaacd69af61ed664f2fe483a4b91c098695bd650b089eb023406ef8744d17b9ff4c8340e95adb4825638b637e8e00bb240a24c8e352339880794a9e7a4b9e59afce0f44d578eae5184357f3d9d7d53d6143c972be650140189fef4505198a515dd0cbbc4c65c4719143133c7bb4be1b612ed268119e1f081865fa3f0be01642b1d80acb8142c7c71d6c33940cc4c2e555aee47dcff3e81928e82216760d98722d9985aa791a9095741f9388bf9d08e4'

// Data for 8 price updates

const PRICE_UPDATES_8 = '504e41550100000000a0010000000001003b981bae635c637bbfa5ef200269201c5edeed62008ace28a0f20157aafd40cc18b63b10a947ff473bdc8295460bc49a5648059133c916107086d9819d1f48e3006537f2ea00000000001ae101faedac5851e32b9b23b5f9411a8c2bac4aae3ed4dd7b811dd1a72ea4aa710000000001f493b1014155575600000000000657310200002710395b432f2ca397535577362552b290a98c25eb9f0800550008f781a893bc9340140c5f89c8a96f438bcfae4d1474cc0f688e3a52892c731800000000009707110000000000000e28fffffff8000000006537ef40000000006537ef3e0000000000973516000000000000147f0a59298821406ca1058371d8140770f3e5e4f7793d229352c0ddaacd69af61ed664f2fe483a4b91c098695bd650b089eb023406ef8744d17b9ff4c8340e95adb4825638b637e8e00bb240a24c8e352339880794a9e7a4b9e59afce0f44d578eae5184357f3d9d7d53d6143c972be650140189fef4505198a515dd0cbbc4c65c4719143133c7bb4be1b612ed268119e1f081865fa3f0be01642b1d80acb8142c7c71d6c33940cc4c2e555aee47dcff3e81928e82216760d98722d9985aa791a9095741f9388bf9d08e4005500f9c0172ba10dfa4d19088d94f5bf61d3b54d5bd7483a322a982e1373ee8ea31b0000031515fb7e7f000000003d460900fffffff8000000006537ef42000000006537ef40000003164822bd0000000000405ab6f40a9d741e1c0b438b0786252b0b1b78c71a6e846b9a12038f37d83fa28241a833f0707567b562c58dd7939933aaa7d1d1eab5c043883d0295cb2e3e1f1da2de1744755ba09d0c2781a1814ee86b1c88a3ef0e7a8af5582367b6c4f44189fc6a4c75c9df51b664c8958569f367c0fd6b719ddb9ae37649e41a39e1e8606e4f44aea70a2298a0e6f639d1c62ef53c8fb6b09df1e2876bb92890a4141a8297f4d93df70ecad021e3549eff1f4265649f8c4bc8b7892109760d98722d9985aa791a9095741f9388bf9d08e4005500ca80ba6dc32e08d06f1aa886011eed1d77c77be9eb761cc10d72b7d0a2fd57a600000029939255600000000002a70420fffffff8000000006537ef42000000006537ef4000000029cfa8cf70000000000387ae510a1d1dd7209603c893569db5aa650918fe1d47a096b99b8a314f619c788e174ec81fd73a7565350e292085df5ed74d14908fc6e13dba769767e9baf419ec36b645885171d33ab7cbb9b67d744619b6733ce3d16dc5928957e66ea48bb125cc6dbddc1bf76f2e53ce2e6d0abb20383cd8c844e19a69a9863ba058613f2263b08274f8bd107c36ca3605892b67818fb6b09df1e2876bb92890a4141a8297f4d93df70ecad021e3549eff1f4265649f8c4bc8b7892109760d98722d9985aa791a9095741f9388bf9d08e400550041f3625971ca2ed2263e78573fe5ce23e13d2558ed3f2e47ab0f84fb9e7ae7220000000005f5e8cf0000000000007d63fffffff8000000006537ef42000000006537ef410000000005f5e51f00000000000068340a03866e64ecdae6eaf9a43adf7100dd71d1fc0fd10fdb4403939f894e15b9894cdfb1572fa059cc3d9b0c96f32c63b9e374cb4892f3bf97d3f0cbf99f0ca3915fb928eff5b40a732305b40a5187638a28e2910992019402a3e8cb55467b3aaf61a9c5b573b5071c3817ed7cb637e513b85a211e9fa4eef4351509666b9227e6397ce2de68556af6f48f9fa38d119e1f081865fa3f0be01642b1d80acb8142c7c71d6c33940cc4c2e555aee47dcff3e81928e82216760d98722d9985aa791a9095741f9388bf9d08e40055001fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c15880000000005f5f8a200000000000061d9fffffff8000000006537ef42000000006537ef3d0000000005f5ec7e00000000000060fc0a4eb367b120168fcadd695187733f46030038eba1a42df786f8db0ba05a9151012d09b5804114e5a625aa7df2e8532a395648822bb860face07c86280faa230a55c5e468d438e4ae3f3ac780d5fee60c93ae82575263d4121f1ca6ae6df79a436d3522d8ba944cf8eb25d67617bb8b7ed025406da31051a3f5dd0cbbc4c65c4719143133c7bb4be1b612ed268119e1f081865fa3f0be01642b1d80acb8142c7c71d6c33940cc4c2e555aee47dcff3e81928e82216760d98722d9985aa791a9095741f9388bf9d08e4005500bfaf7739cb6fe3e1c57a0ac08e1d931e9e6062d476fa57804e165ab572b5b621000000000355c8570000000000004d16fffffff8000000006537ef44000000006537ef4200000000035acd3a00000000000057140a1accb5e284dcfc29d279f51748f26bd12e9e9c717c99890596b16bd33202336c36e6667eef86c23c9c5054ed701d1bbb1b53130b8c747bb12d78b89a254720b7d1e47ed515b630b18d4523307200eaeb8c29e83c21a9ffc53ac8b34f0ec35c4649aee0f82e53ce2e6d0abb20383cd8c844e19a69a9863ba058613f2263b08274f8bd107c36ca3605892b67818fb6b09df1e2876bb92890a4141a8297f4d93df70ecad021e3549eff1f4265649f8c4bc8b7892109760d98722d9985aa791a9095741f9388bf9d08e4005500a36c0b485ebb9bbaf0d182d8208e7a2c2ae138e69f47712085d4166f1c847dbb0000000000275650000000000000c454fffffffb000000006537ef46000000006537ef440000000000277ffa00000000000010090a2a99cbec1b36006a5ab08966513ed6844c1a3b96448dc2102cc3b9635713039dbe1fc79be2a7c184b9f2d4a4305f76d663880efe9375c2c3aaf5e8338b499481993fdd1f4b88db1bd21bd81e997ace79735aa5c4a993b07e0cb2c2bc5011ad901b3a8a04b7a28ffed1d336e88a6cc73c9bff93b5b06344f2738d4a96146fbd8b62d01854514e4c827ae7a54c8b3c69f73decf6f20e237bf11d3d5f30dc1bc5af1d6c33940cc4c2e555aee47dcff3e81928e82216760d98722d9985aa791a9095741f9388bf9d08e4005500c21e81af5c80ee23c0b51c8b4f4ba0ea28c8b38bc85beb7b1335356a3202325600000000000e9a480000000000006a43fffffffb000000006537ef44000000006537ef4200000000000ec00100000000000005000a9b525b6ef14d20e95bd27cc0d3fd55fd815a231dbd4c5c8c8b083e8b7db9d3a81a8be1a35aae628984e7da9fd322080ad3caa0da5994832adb139e9c91c5adf2d0b5afd7b45140d99fe7445af207453e8c29e83c21a9ffc53ac8b34f0ec35c4649aee0f82e53ce2e6d0abb20383cd8c844e19a69a9863ba058613f2263b08274f8bd107c36ca3605892b67818fb6b09df1e2876bb92890a4141a8297f4d93df70ecad021e3549eff1f4265649f8c4bc8b7892109760d98722d9985aa791a9095741f9388bf9d08e4'

// ===============================================================================================================

let pclib: PricecasterLib
let algodClient: algosdk.Algodv2
let creatorAccount: algosdk.Account
let operatorAccount: algosdk.Account
let quantAccount: algosdk.Account
type AssetMapEntry = { decimals: number, assetId: number | undefined, samplePrice: number, exponent: number, slot: number | undefined }
const asaInSlot = Array(62).fill(0)

const assetMap1: AssetMapEntry[] = [
  { decimals: 5, assetId: undefined, samplePrice: 10000, exponent: -8, slot: undefined },
  { decimals: 6, assetId: undefined, samplePrice: 10000, exponent: -7, slot: undefined },
  { decimals: 7, assetId: undefined, samplePrice: 10000, exponent: -6, slot: undefined },
  { decimals: 8, assetId: undefined, samplePrice: 10000, exponent: -5, slot: undefined },
  { decimals: 3, assetId: undefined, samplePrice: 10000, exponent: -4, slot: undefined },
  { decimals: 8, assetId: undefined, samplePrice: 10000, exponent: -5, slot: undefined },
  { decimals: 8, assetId: undefined, samplePrice: 10000, exponent: -5, slot: undefined },
  { decimals: 3, assetId: undefined, samplePrice: 10000, exponent: -4, slot: undefined }
]

const SYSTEM_SLOT_INDEX = 85
const SLOT_SIZE = 92

const DEFAULT_PUB_TIME = '000000009fff8888'
const SLOT_PUB_TIME_FIELD_OFFSET = 52

const DUMMY_MERKLE_ROOT = Buffer.from('0000000000000000000000000000000000000000', 'hex')

// ===============================================================================================================

async function createPricecasterApp (coreId: number, testMode: boolean, disableMerkleVerification: boolean = false) {
  const out = spawnSync(testConfig.PYTHON_BIN, [testConfig.PYTEALSOURCE])
  if (out.error) {
    throw new Error(out.error.toString())
  }

  if (out.status !== 0) {
    throw new Error(out.stderr.toString())
  }

  console.log(out.output.toString())

  console.log('Deploying Pricecaster V2 Application...')
  const txId = await pclib.createPricecasterApp(
    creatorAccount.addr,
    operatorAccount.addr,
    quantAccount.addr,
    coreId, testMode, disableMerkleVerification, signCallback, 3000)
  console.log('txId: ' + txId)
  const txResponse = await pclib.waitForTransactionResponse(txId)
  const pkAppId = pclib.appIdFromCreateAppResponse(txResponse)
  pclib.setAppId(PRICECASTER_CI, pkAppId)

  return pkAppId
}

function signCallback (sender: string, tx: Transaction) {
  return tx.signTxn(creatorAccount.sk)
}

async function createAsset (decimals: number): Promise<number> {
  const params = await algodClient.getTransactionParams().do()
  params.fee = 1000
  params.flatFee = true

  const tx = algosdk.makeAssetCreateTxnWithSuggestedParams(
    creatorAccount.addr,
    undefined,
    1_000_000,
    decimals,
    false,
    creatorAccount.addr,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    params)

  const { txId } = await algodClient.sendRawTransaction(tx.signTxn(creatorAccount.sk)).do()
  const txResponse = await pclib.waitForTransactionResponse(txId)
  return pclib.assetIdFromCreateAppResponse(txResponse)
}

async function deleteAsset (assetId: number): Promise<string> {
  const params = await algodClient.getTransactionParams().do()
  params.fee = 1000

  const tx = algosdk.makeAssetDestroyTxnWithSuggestedParams(
    creatorAccount.addr,
    undefined,
    assetId,
    params)

  const { txId } = await algodClient.sendRawTransaction(tx.signTxn(creatorAccount.sk)).do()
  await pclib.waitForTransactionResponse(txId)
  return txId
}

function prepareTestPriceUpdate (assetMap: AssetMapEntry[], pubtime_: string = DEFAULT_PUB_TIME): Buffer {
  const updateCount = Buffer.alloc(1)
  updateCount.writeUInt8(assetMap.length)

  const UPDATE_ENTRY_SIZE = 0x55
  const updateEntrySize = Buffer.alloc(3)
  updateEntrySize.writeUInt16BE(UPDATE_ENTRY_SIZE, 0)
  updateEntrySize.writeUInt8(0, 2)

  let payload: Buffer = Buffer.concat([updateCount])

  for (const v of assetMap) {
    const priceId = Buffer.from('aa'.repeat(32), 'hex')
    const price = Buffer.alloc(8)
    price.writeBigUInt64BE(BigInt(v.samplePrice))
    const conf = Buffer.from('cfcfcfcfcfcfcfcf', 'hex')
    const exp = Buffer.alloc(4)
    exp.writeInt32BE(v.exponent)
    const emaPrice = Buffer.from('1111111111111111', 'hex')
    const emaConf = Buffer.from('2222222222222222', 'hex')
    const pubtime = Buffer.from(pubtime_, 'hex')
    const prevPubtime = Buffer.from('0000000000000000', 'hex')

    // add some bogus merkle-path
    const merklePathLen = Buffer.alloc(1)
    merklePathLen.writeUInt8(2)
    const merklePath = Buffer.concat([Buffer.from('01'.repeat(20), 'hex'), Buffer.from('02'.repeat(20), 'hex')])

    payload = Buffer.concat([payload, updateEntrySize, priceId, price, conf, exp, pubtime, prevPubtime, emaPrice, emaConf, merklePathLen, merklePath])
  }

  return payload
}

async function createAssets (assetMap: AssetMapEntry[]) {
  for (const [i, val] of assetMap.entries()) {
    if (assetMap[i].assetId === undefined) {
      assetMap[i].assetId = await createAsset(val.decimals)
    }
  }
}

async function deleteAssets (assetMap: AssetMapEntry[]) {
  for (const asset of assetMap) {
    if (asset.assetId !== undefined) {
      await deleteAsset(asset.assetId!)
    }
  }
}

async function sendPriceStoreTx (assetMap: AssetMapEntry[], priceUpdate: Buffer) {
  const params = await algodClient.getTransactionParams().do()
  params.fee = 4000 * (3500 + assetMap.length * 1000)

  const tx = pclib.makePriceStoreTx(operatorAccount.addr,
    DUMMY_MERKLE_ROOT,
    assetMap.map((v, i) => { return { asaid: v.assetId!, slot: v.slot! } }),
    priceUpdate,
    params, 2500)

  const { txId } = await algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()
  return await pclib.waitForTransactionResponse(txId)
}

async function sendAllocSlotTx (assetId: number) {
  const params = await algodClient.getTransactionParams().do()
  params.fee = 1000

  const tx = pclib.makeAllocSlotTx(quantAccount.addr, assetId, params)
  const { txId } = await algodClient.sendRawTransaction(tx.signTxn(quantAccount.sk)).do()
  return await pclib.waitForTransactionResponse(txId)
}

async function testOkCase (decimals: number,
  samplePrice: number,
  exponent: number,
  assetIdOverride?: number): Promise<PriceSlotData> {
  const assetMap = [
    { decimals, assetId: assetIdOverride, samplePrice, exponent, slot: -1 }
  ]

  await createAssets(assetMap)
  const txResponse = await sendAllocSlotTx(assetMap[0].assetId!)
  assetMap[0].slot = Number(Buffer.from(txResponse.logs[0]).readBigUInt64BE(6))

  const priceUpdate = prepareTestPriceUpdate(assetMap)
  const priceUpdateChop = priceUpdate.subarray(4 + 32) // Skip number of prices and size (NN, SSSS, 00)

  const txResponse2 = await sendPriceStoreTx(assetMap, priceUpdate)
  expect(txResponse2['pool-error']).to.equal('')

  const slotData = await pclib.readSlot(assetMap[0].slot)
  const asaId = slotData.subarray(0, 8).readBigInt64BE()
  const normalizedPrice = slotData.subarray(8, 16).readBigUint64BE()
  const price = slotData.subarray(16, 24).readBigUint64BE()
  const confidence = slotData.subarray(24, 32).readBigUint64BE()
  const exp = slotData.subarray(32, 36).readInt32BE()
  const priceEMA = slotData.subarray(36, 44).readBigUint64BE()
  const confEMA = slotData.subarray(44, 52).readBigUint64BE()
  const pubTime = slotData.subarray(52, 60).readBigUint64BE()
  const prevPubTime = slotData.subarray(60, 68).readBigUint64BE()
  const np = BigInt(Math.floor(assetMap[0].samplePrice * Math.pow(10, (12 + assetMap[0].exponent - (assetIdOverride === 0 ? 6 : assetMap[0].decimals)))))
  const logPrefix = (np === 0n ? 'NORM_PRICE_ZERO@' : 'STORE@')
  expect(slotData.length).to.equal(SLOT_SIZE)

  const loggedData = (np !== 0n
    ? slotData
    : Buffer.concat([algosdk.encodeUint64(assetMap[0].assetId!), // asaId
      Buffer.from('00'.repeat(8), 'hex'), // normalized price
      priceUpdateChop.subarray(0, 20),
      priceUpdateChop.subarray(20 + 16, 20 + 32),
      priceUpdateChop.subarray(20, 20 + 16),
      Buffer.from('00'.repeat(24), 'hex')
    ]))

  expect(txResponse2.logs[0].length).to.equal(logPrefix.length + 8 + slotData.length)

  expect(Buffer.from(txResponse2.logs[0]).toString('hex')).to.deep.equal(
    Buffer.from(logPrefix).toString('hex') + Buffer.from(algosdk.encodeUint64(assetMap[0].slot)).toString('hex') + loggedData.toString('hex'))

  // This test will work for testing 1-sized updates ONLY!

  if (np !== 0n) {
    expect(slotData.subarray(0, 8).readBigUInt64BE()).to.deep.equal(BigInt(assetMap[0].assetId!))
    expect(normalizedPrice).to.deep.equal(np)
    expect(price).to.deep.equal(priceUpdateChop.subarray(0, 8).readBigUInt64BE()) // price
    expect(confidence).to.deep.equal(priceUpdateChop.subarray(8, 16).readBigUInt64BE()) // conf
    expect(exp).to.deep.equal(priceUpdateChop.subarray(16, 20).readInt32BE()) // exp
    expect(priceEMA).to.deep.equal(priceUpdateChop.subarray(36, 44).readBigUInt64BE()) // priceEMA
    expect(confEMA).to.deep.equal(priceUpdateChop.subarray(44, 52).readBigUint64BE()) // confEMA
    expect(pubTime).to.deep.equal(priceUpdateChop.subarray(20, 28).readBigUint64BE()) // pubtime
    expect(prevPubTime).to.deep.equal(priceUpdateChop.subarray(28, 36).readBigUInt64BE()) // prev pubtime
    expect(slotData.subarray(68, 92)).to.deep.equal(Buffer.from(new Uint8Array(24).fill(0))) // zeroed slot
  }

  await deleteAssets(assetMap)
  return {
    asaId: parseInt(asaId.toString()),
    pythPrice: price,
    normalizedPrice,
    confidence,
    exponent: exp,
    priceEMA,
    confEMA,
    pubTime,
    prevPubTime,
    attTime: 0n,
    prevPrice: 0n,
    prevConf: 0n
  }
}

async function testFailCase (decimals: number,
  samplePrice: number,
  exponent: number,
  assetIdOverride?: number,
  sender: Account = operatorAccount,
  failedLine?: number) {
  const assetMap = [
    { decimals, assetId: assetIdOverride, samplePrice, exponent, slot: undefined }
  ]

  await createAssets(assetMap)
  const priceUpdate = prepareTestPriceUpdate(assetMap)

  const params = await algodClient.getTransactionParams().do()
  params.fee = 4000 + (3500 + assetMap.length * 1000)
  const tx = pclib.makePriceStoreTx(sender.addr, DUMMY_MERKLE_ROOT,
    assetMap.map((v, i) => { return { asaid: v.assetId!, slot: i } }),
    priceUpdate,
    params, 2500)

  const regex = new RegExp(failedLine ? `logic eval error.*opcodes=pushint ${failedLine}` : 'logic eval error')

  await expect(algodClient.sendRawTransaction(tx.signTxn(sender.sk)).do()).to.be.rejectedWith(regex)

  if (!assetIdOverride) {
    deleteAssets(assetMap)
  }
}

async function testOverflowCase (decimals: number,
  // eslint-disable-next-line camelcase
  samplePrice: number,
  exponent: number,
  assetIdOverride?: number,
  sender: Account = operatorAccount) {
  const assetMap = [
    { decimals, assetId: assetIdOverride, samplePrice, exponent, slot: -1 }
  ]

  await createAssets(assetMap)
  const priceUpdate = prepareTestPriceUpdate(assetMap)
  const txResponse = await sendAllocSlotTx(assetMap[0].assetId!)
  assetMap[0].slot = Number(Buffer.from(txResponse.logs[0]).readBigUInt64BE(6))

  const params = await algodClient.getTransactionParams().do()
  params.fee = 4000 + (3500 + assetMap.length * 1000)
  const tx = pclib.makePriceStoreTx(sender.addr, DUMMY_MERKLE_ROOT,
    assetMap.map((v, i) => { return { asaid: v.assetId!, slot: v.slot } }),
    priceUpdate,
    params, 2500)

  const regex = /opcodes=swap; !; assert$/gm
  await expect(algodClient.sendRawTransaction(tx.signTxn(sender.sk)).do()).to.be.rejectedWith(regex)
}
// ===============================================================================================================
//
// Test suite starts here
//
// ===============================================================================================================

describe('Pricecaster App Tests', function () {
  before(async function () {
    creatorAccount = algosdk.mnemonicToSecretKey(testConfig.CREATOR_MNEMO)
    operatorAccount = algosdk.mnemonicToSecretKey(testConfig.OPERATOR_MNEMO)
    quantAccount = algosdk.mnemonicToSecretKey(testConfig.QUANT_MNEMO)
    algodClient = new algosdk.Algodv2(testConfig.ALGORAND_NODE_TOKEN, testConfig.ALGORAND_NODE_HOST, testConfig.ALGORAND_NODE_PORT)
    pclib = new PricecasterLib(algodClient)
  }
  )

  after(async function () {
    await pclib.deleteApp(creatorAccount.addr, signCallback, PRICECASTER_CI)
    // await deleteAllAssets()
  })

  // -----------------------------------------------------------------------------------------------

  it('Must create pricecaster V2 app with Core app id set, Test Mode Disabled', async function () {
    const dummyCoreId = 10000
    await createPricecasterApp(dummyCoreId, false)
    console.log('    - [Created pricecaster appId: %d]', PRICECASTER_CI.appId)

    const thisCoreId = await pclib.readCoreId()
    expect(thisCoreId).to.equal(BigInt(dummyCoreId))
  })

  // -----------------------------------------------------------------------------------------------

  it('Must fail to call store out-of-group, without Testing bit set', async function () {
    await testFailCase(19, 1, 0, 50000000, undefined, 308)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must fail to call setflags from non-creator account', async function () {
    const altAccount = generateAccount()
    const paymentTx = makePaymentTxnWithSuggestedParams(creatorAccount.addr, altAccount.addr, 400000, undefined, undefined, await algodClient.getTransactionParams().do())
    const params = await algodClient.getTransactionParams().do()
    const paymentTxId = await algodClient.sendRawTransaction(paymentTx.signTxn(creatorAccount.sk)).do()

    await algosdk.waitForConfirmation(algodClient, paymentTxId.txId, 4)
    const tx = pclib.makeSetFlagsTx(altAccount.addr, 128, params)
    // eslint-disable-next-line prefer-regex-literals
    const regex = new RegExp('logic eval error.*opcodes=pushint 431')
    await expect(algodClient.sendRawTransaction(tx.signTxn(altAccount.sk)).do()).to.be.rejectedWith(regex)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must set setflags (testmode) by creator', async function () {
    const params = await algodClient.getTransactionParams().do()
    const tx = pclib.makeSetFlagsTx(creatorAccount.addr, 0xff, params)
    const { txId } = await algodClient.sendRawTransaction(tx.signTxn(creatorAccount.sk)).do()
    const txResponse = await pclib.waitForTransactionResponse(txId)
    expect(txResponse['pool-error']).to.equal('')
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0b00111111)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must create pricecaster V2 app with Core app id set, Test Mode Enabled, Merkle-Verification Enabled', async function () {
    const dummyCoreId = 10001
    await createPricecasterApp(dummyCoreId, true, false)
    console.log('    - [Created pricecaster appId: %d]', PRICECASTER_CI.appId)

    const thisCoreId = await pclib.readCoreId()
    expect(thisCoreId).to.equal(BigInt(dummyCoreId))
  })

  // -----------------------------------------------------------------------------------------------

  it('Must have system flags set to 0x80 with Test deployment', async function () {
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must fail to store unallocated slot 0', async function () {
    const params = await algodClient.getTransactionParams().do()
    params.fee = 4000

    const priceUpdateBuf = Buffer.from(PRICE_UPDATE_1, 'hex')

    const { merkleRoot } = pclib.extractVaaMerkleRoot(priceUpdateBuf)
    const priceUpdates = pclib.extractPriceUpdatesBlock(priceUpdateBuf)

    const tx = pclib.makePriceStoreTx(operatorAccount.addr, merkleRoot, [{ asaid: asaInSlot[0], slot: 0 }], priceUpdates, params, 2500)

    const regex = /logic eval error.*opcodes=pushint 184/
    await expect(algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()).to.be.rejectedWith(regex)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must succeed to allocate slot 0 for new ASA ID', async function () {
    const assetMap = [
      { decimals: 5, assetId: undefined, samplePrice: 10000, exponent: -8, slot: undefined }
    ]

    await createAssets(assetMap)
    const txResponse = await sendAllocSlotTx(assetMap[0].assetId!)
    expect(txResponse['pool-error']).to.equal('')

    const ec = (await pclib.readSystemSlot()).entryCount
    expect(txResponse.logs[0]).to.deep.equal(Buffer.concat([Buffer.from('ALLOC@'), Buffer.from(algosdk.encodeUint64(ec - 1))]))

    asaInSlot[0] = assetMap[0].assetId!

    // Make sure flags were untouched
    const flags = (await pclib.readSystemSlot()).flags
    expect(flags).to.equal(0x80)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must fail to store data in incorrect slot', async function () {
    await testFailCase(19, 1, 0, 85000000, undefined, 353)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must fail to store with incorrect merkle root length', async function () {
    const params = await algodClient.getTransactionParams().do()
    params.fee = 2500

    const priceUpdateBuf = Buffer.from(PRICE_UPDATE_1, 'hex')

    const { merkleRoot } = pclib.extractVaaMerkleRoot(priceUpdateBuf)
    const priceUpdates = pclib.extractPriceUpdatesBlock(priceUpdateBuf)

    const tx = pclib.makePriceStoreTx(operatorAccount.addr, merkleRoot.subarray(1), [{ asaid: asaInSlot[0], slot: 0 }], priceUpdates, params, 2500)

    // eslint-disable-next-line prefer-regex-literals
    const regex = new RegExp('logic eval error.*opcodes=pushint 305')
    await expect(algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()).to.be.rejectedWith(regex)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must fail to store with invalid proof', async function () {
    const PRICE_UPDATE_INVALID_PROOF = '504e41550100000000a00100000000010015abb882e249e8e414888cb148cfa95be92adf49736198d7a9493c14d4bc23f81adff5e793a29fdb8375b757006be1a97e21c203a7d5b81d2e99f46a95a10c530064db75a300000000001ae101faedac5851e32b9b23b5f9411a8c2bac4aae3ed4dd7b811dd1a72ea4aa71000000000109af590141555756000000000005652009000027107ff51bb3cbacc521b08069a66762e9a1be36ff440100550008f781a893bc9340140c5f89c8a96f438bcfae4d1474cc0f688e3a52892c73180000000000abe0340000000000001c5efffffff80000000064db75a30000000064db75a20000000000ac1dc20000000000001874096cd1a2393b714f0d4f6870759a761bc34abfda96a90639d50570f28cd864113821db528c11bbe7bb92ffcc3d2c25ad6f2e4f4dc22f393967d25cf4b8df0450f6b0548419986d1403a9624aa2973d45adfe1f2380720d78f904bbed1053bc0e30f3ae4bc8dafd338aabef799bea87bdab879a78dfd8ef9037fd5d875cae9f95ce51a7b4576f6032273f851df646e2ac1d53a1fa5726854aeb150d5afd9a6e4ca6a9810c0dda7904f7c3ef6d7a82c27f7e7259f298'
    const params = await algodClient.getTransactionParams().do()
    params.fee = 4000

    const priceUpdateBuf = Buffer.from(PRICE_UPDATE_INVALID_PROOF, 'hex')

    const { merkleRoot } = pclib.extractVaaMerkleRoot(priceUpdateBuf)
    const priceUpdates = pclib.extractPriceUpdatesBlock(priceUpdateBuf)

    const tx = pclib.makePriceStoreTx(operatorAccount.addr, merkleRoot, [{ asaid: asaInSlot[0], slot: 0 }], priceUpdates, params, 2500)

    // eslint-disable-next-line prefer-regex-literals
    const regex = new RegExp('logic eval error.*opcodes=pushint 356')
    await expect(algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()).to.be.rejectedWith(regex)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must handle one price update at index 0 with enough opcode budget', async function () {
    const params = await algodClient.getTransactionParams().do()
    params.fee = 4000

    const priceUpdateBuf = Buffer.from(PRICE_UPDATE_1, 'hex')

    const { merkleRoot } = pclib.extractVaaMerkleRoot(priceUpdateBuf)
    const priceUpdates = pclib.extractPriceUpdatesBlock(priceUpdateBuf)

    const tx = pclib.makePriceStoreTx(operatorAccount.addr, merkleRoot, [{ asaid: asaInSlot[0], slot: 0 }], priceUpdates, params, 2500)

    const { txId } = await algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()
    const txResponse = await pclib.waitForTransactionResponse(txId)
    expect(txResponse['pool-error']).to.equal('')

    const slotData = await pclib.readSlot(0)
    const priceUpdateChop = priceUpdates.subarray(4 + 32) // Skip number of prices and size (NN, SSSS, 00)
    expect(slotData.subarray(0, 8).readBigUInt64BE()).to.deep.equal(BigInt(asaInSlot[0]))

    // TODO: check Normalized price!
    // expect(priceData.subarray(8, 16).readBigUInt64BE()).to.deep.equal(normalized_price)
    expect(slotData.subarray(16, 24)).to.deep.equal(priceUpdateChop.subarray(0, 8)) // price
    expect(slotData.subarray(24, 32)).to.deep.equal(priceUpdateChop.subarray(8, 16)) // conf
    expect(slotData.subarray(32, 36).readInt32BE()).to.deep.equal(priceUpdateChop.subarray(16, 20).readInt32BE()) // exp
    expect(slotData.subarray(36, 44)).to.deep.equal(priceUpdateChop.subarray(36, 44)) // priceEMA
    expect(slotData.subarray(44, 52)).to.deep.equal(priceUpdateChop.subarray(44, 52)) // confEMA
    expect(slotData.subarray(52, 60)).to.deep.equal(priceUpdateChop.subarray(20, 28)) // pubtime
    expect(slotData.subarray(60, 68)).to.deep.equal(priceUpdateChop.subarray(28, 36)) // prev pubtime
    expect(slotData.subarray(68, 92)).to.deep.equal(Buffer.from(new Uint8Array(24).fill(0))) // zeroed slot
  })

  // -----------------------------------------------------------------------------------------------

  it('Must allocate eight additional slots', async function () {
    await createAssets(assetMap1)

    const params = await algodClient.getTransactionParams().do()
    params.fee = 1000

    for (const asset of assetMap1) {
      const tx = pclib.makeAllocSlotTx(quantAccount.addr, asset.assetId!, params)
      const { txId } = await algodClient.sendRawTransaction(tx.signTxn(quantAccount.sk)).do()
      const txResponse = await pclib.waitForTransactionResponse(txId)
      expect(txResponse['pool-error']).to.equal('')

      const ec = (await pclib.readSystemSlot()).entryCount
      expect(txResponse.logs[0]).to.deep.equal(Buffer.concat([Buffer.from('ALLOC@'), Buffer.from(algosdk.encodeUint64(ec - 1))]))
      asset.slot = parseInt(Buffer.from(txResponse.logs[0]).readBigUInt64BE(6).toString())

      asaInSlot[asset.slot!] = asset.assetId!
    }
  })

  // -----------------------------------------------------------------------------------------------

  it('Must handle max eight price updates at index 0-7 with enough opcode budget', async function () {
    const params = await algodClient.getTransactionParams().do()
    params.fee = 30000

    const priceUpdateBuf = Buffer.from(PRICE_UPDATES_8, 'hex')

    const { merkleRoot } = pclib.extractVaaMerkleRoot(priceUpdateBuf)
    const priceUpdates = pclib.extractPriceUpdatesBlock(priceUpdateBuf)

    const tx = pclib.makePriceStoreTx(operatorAccount.addr, merkleRoot,
      assetMap1.map((v, i) => { return { asaid: v.assetId!, slot: v.slot! } }), priceUpdates, params, 20000)

    const { txId } = await algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()
    const txResponse = await pclib.waitForTransactionResponse(txId)
    expect(txResponse['pool-error']).to.equal('')

    let i = 0
    for (const v of assetMap1) {
      const slotData = await pclib.readSlot(Number(v.slot!))
      const chopIndex = 4 + (i * 288) + 32 // Skip number of prices and size (NN, SSSS, 00)
      const priceUpdateChop = priceUpdates.subarray(chopIndex, chopIndex + 233)
      expect(slotData.subarray(0, 8).readBigUInt64BE()).to.deep.equal(BigInt(asaInSlot[v.slot!]))

      // TODO: check Normalized price!
      // expect(priceData.subarray(8, 16).readBigUInt64BE()).to.deep.equal(normalized_price)
      expect(slotData.subarray(16, 24)).to.deep.equal(priceUpdateChop.subarray(0, 8)) // price
      expect(slotData.subarray(24, 32)).to.deep.equal(priceUpdateChop.subarray(8, 16)) // conf
      expect(slotData.subarray(32, 36).readInt32BE()).to.deep.equal(priceUpdateChop.subarray(16, 20).readInt32BE()) // exp
      expect(slotData.subarray(36, 44)).to.deep.equal(priceUpdateChop.subarray(36, 44)) // priceEMA
      expect(slotData.subarray(44, 52)).to.deep.equal(priceUpdateChop.subarray(44, 52)) // confEMA
      expect(slotData.subarray(52, 60)).to.deep.equal(priceUpdateChop.subarray(20, 28)) // pubtime
      expect(slotData.subarray(60, 68)).to.deep.equal(priceUpdateChop.subarray(28, 36)) // prev pubtime
      expect(slotData.subarray(68, 92)).to.deep.equal(Buffer.from(new Uint8Array(24).fill(0))) // zeroed slot

      i++
    }

    await deleteAssets(assetMap1)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must create pricecaster V2 app with Core app id set, Test Mode Enabled, Merkle-Verification DISABLED', async function () {
    const dummyCoreId = 10002
    await createPricecasterApp(dummyCoreId, true, true)
    console.log('    - [Created pricecaster appId: %d]', PRICECASTER_CI.appId)

    const thisCoreId = await pclib.readCoreId()
    expect(thisCoreId).to.equal(BigInt(dummyCoreId))
  })

  // -----------------------------------------------------------------------------------------------

  it('Must have system flags set to 0x80 OR 0x40 with Test deployment and disabled merkle verif flag set', async function () {
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80 | 0x40)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must succeed to store with invalid proof  with  disabled merkle verif flag set', async function () {
    // Allocate slot
    const assetMap = [
      { decimals: 5, assetId: undefined, samplePrice: 10000, exponent: -8, slot: undefined }
    ]

    await createAssets(assetMap)
    let txResponse = await sendAllocSlotTx(assetMap[0].assetId!)
    expect(txResponse['pool-error']).to.equal('')

    const ec = (await pclib.readSystemSlot()).entryCount
    expect(txResponse.logs[0]).to.deep.equal(Buffer.concat([Buffer.from('ALLOC@'), Buffer.from(algosdk.encodeUint64(ec - 1))]))

    // Send update with invalid proof

    asaInSlot[0] = assetMap[0].assetId!
    const PRICE_UPDATE_INVALID_PROOF = '504e41550100000000a00100000000010015abb882e249e8e414888cb148cfa95be92adf49736198d7a9493c14d4bc23f81adff5e793a29fdb8375b757006be1a97e21c203a7d5b81d2e99f46a95a10c530064db75a300000000001ae101faedac5851e32b9b23b5f9411a8c2bac4aae3ed4dd7b811dd1a72ea4aa71000000000109af590141555756000000000005652009000027107ff51bb3cbacc521b08069a66762e9a1be36ff440100550008f781a893bc9340140c5f89c8a96f438bcfae4d1474cc0f688e3a52892c73180000000000abe0340000000000001c5efffffff80000000064db75a30000000064db75a20000000000ac1dc20000000000001874096cd1a2393b714f0d4f6870759a761bc34abfda96a90639d50570f28cd864113821db528c11bbe7bb92ffcc3d2c25ad6f2e4f4dc22f393967d25cf4b8df0450f6b0548419986d1403a9624aa2973d45adfe1f2380720d78f904bbed1053bc0e30f3ae4bc8dafd338aabef799bea87bdab879a78dfd8ef9037fd5d875cae9f95ce51a7b4576f6032273f851df646e2ac1d53a1fa5726854aeb150d5afd9a6e4ca6a9810c0dda7904f7c3ef6d7a82c27f7e7259f298'
    const params = await algodClient.getTransactionParams().do()
    params.fee = 30000

    const priceUpdateBuf = Buffer.from(PRICE_UPDATE_INVALID_PROOF, 'hex')

    const { merkleRoot } = pclib.extractVaaMerkleRoot(priceUpdateBuf)
    const priceUpdates = pclib.extractPriceUpdatesBlock(priceUpdateBuf)

    const tx = pclib.makePriceStoreTx(operatorAccount.addr, merkleRoot, [{ asaid: asaInSlot[0], slot: 0 }], priceUpdates, params, 20000)

    const { txId } = await algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()
    txResponse = await pclib.waitForTransactionResponse(txId)
    // eslint-disable-next-line prefer-regex-literals
    expect(txResponse['pool-error']).to.equal('')
  })

  // -----------------------------------------------------------------------------------------------

  it('Must handle boundary case d=19 e=12', async function () {
    // Ensure we have disabled merkle-proof
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80 | 0x40)
    await testOkCase(19, 1, 12)
  })

  it('Must handle boundary case d=19 e=-12', async function () {
    // Ensure we have disabled merkle-proof
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80 | 0x40)
    await testOkCase(19, 1, -12)
  })

  it('Must fail boundary case d=0 e=12', async function () {
    await testFailCase(0, 1, 12)
  })

  it('Must handle boundary case d=0 e=-12', async function () {
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80 | 0x40)
    await testOkCase(0, 1, -12)
  })

  it('Must handle zero exponent case (d=0)', async function () {
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80 | 0x40)
    await testOkCase(0, 1, 0)
  })

  it('Must handle zero exponent case (d=19)', async function () {
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80 | 0x40)
    await testOkCase(19, 1, 0)
  })

  it('Must handle asset 0 (ALGO) as 6 decimal asset', async function () {
    // Will substitute bogus 9999999999 decimals to 6 since asset 0 is interpreted as 6 decimal (ALGO)
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80 | 0x40)
    await testOkCase(9999999999, 100000, -8, 0)
  })

  it('Must handle case zero exponent (d=0), with max 18_446_744 price', async function () {
    const ssi = await pclib.readSystemSlot()
    expect(ssi.flags).to.equal(0x80 | 0x40)
    await testOkCase(0, 18_446_744, 0)
  })

  it('Must fail on zero exponent (d=0), with > 18_446_744 price (overflow)', async function () {
    await testOverflowCase(0, 18_446_745, 0)
  })

  it('Must fail to store unknown asset ID', async function () {
    await testFailCase(4, 1000, -8, 99999999999)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must fail to publish when VAA attestations and ASA ID argument count differ', async function () {
    const priceUpdate = prepareTestPriceUpdate(assetMap1)
    const params = await algodClient.getTransactionParams().do()
    params.fee = 7000

    // There are five assets in payload, but only one Asset ID as argument to makeStoretx

    const tx = pclib.makePriceStoreTx(operatorAccount.addr, DUMMY_MERKLE_ROOT,
      [{ asaid: assetMap1[0].assetId!, slot: assetMap1[0].slot! }],
      priceUpdate,
      params, 7000)

    // eslint-disable-next-line prefer-regex-literals
    const regex = new RegExp('logic eval error.*opcodes=pushint 322')
    await expect(algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()).to.be.rejectedWith(regex)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must ignore publication where an attestation has older publish time', async function () {
    const assetMap = [
      { decimals: 5, assetId: asaInSlot[0], samplePrice: 10000, exponent: -8, slot: 0 }
    ]

    await createAssets(assetMap)
    let priceUpdate = prepareTestPriceUpdate(assetMap)
    const params = await algodClient.getTransactionParams().do()
    params.fee = 15000

    let tx = pclib.makePriceStoreTx(operatorAccount.addr, DUMMY_MERKLE_ROOT,
      [{ asaid: assetMap[0].assetId!, slot: assetMap[0].slot! }],
      priceUpdate,
      params, 7000)

    const { txId } = await algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()
    let txResponse = await pclib.waitForTransactionResponse(txId)
    expect(txResponse['pool-error']).to.equal('')

    const slotData = await pclib.readSlot(assetMap[0].slot!)
    expect(slotData.subarray(SLOT_PUB_TIME_FIELD_OFFSET, SLOT_PUB_TIME_FIELD_OFFSET + 8).toString('hex')).to.be.equal(DEFAULT_PUB_TIME)

    // Set a very old time. This must be ignored since a newer previous price is already set.
    priceUpdate = prepareTestPriceUpdate(assetMap, '0000000000000001')

    tx = pclib.makePriceStoreTx(operatorAccount.addr, DUMMY_MERKLE_ROOT,
      [{ asaid: assetMap[0].assetId!, slot: assetMap[0].slot! }],
      priceUpdate,
      params, 7000)

    {
      const { txId } = await algodClient.sendRawTransaction(tx.signTxn(operatorAccount.sk)).do()
      txResponse = await pclib.waitForTransactionResponse(txId)
      expect(txResponse['pool-error']).to.equal('')

      expect(Buffer.from(txResponse.logs[0])).to.deep.equal(Buffer.concat([Buffer.from('PRICE_IGNORED_OLD@'), Buffer.from(algosdk.encodeUint64(asaInSlot[0]))]))
      expect(txResponse['global-state-delta']).to.be.undefined
    }
  })

  // -----------------------------------------------------------------------------------------------

  it('Must zero contract with reset call', async function () {
    const params = await algodClient.getTransactionParams().do()
    params.fee = 2000

    const tx = pclib.makeResetTx(creatorAccount.addr, params)

    const { txId } = await algodClient.sendRawTransaction(tx.signTxn(creatorAccount.sk)).do()
    const txResponse = await pclib.waitForTransactionResponse(txId)
    expect(txResponse['pool-error']).to.equal('')

    const global = await pclib.fetchGlobalSpace()
    const buf = Buffer.alloc(127 * 63)
    // Flags must be present, but entry count set to zero
    buf.writeUint8(0, SLOT_SIZE * SYSTEM_SLOT_INDEX)
    buf.writeUint8(0x80 + 0x40, SLOT_SIZE * SYSTEM_SLOT_INDEX + 1)
    expect(global).to.deep.equal(buf)
  })

  // -----------------------------------------------------------------------------------------------

  it('Must fail to store from non-operator account', async function () {
    const altAccount = generateAccount()
    const paymentTx = makePaymentTxnWithSuggestedParams(creatorAccount.addr, altAccount.addr, 400000, undefined, undefined, await algodClient.getTransactionParams().do())
    const paymentTxId = await algodClient.sendRawTransaction(paymentTx.signTxn(creatorAccount.sk)).do()
    await algosdk.waitForConfirmation(algodClient, paymentTxId.txId, 4)
    await testFailCase(4, 1, -8, undefined, altAccount)
  })
})
