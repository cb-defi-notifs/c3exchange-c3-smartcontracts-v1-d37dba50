
import { HexString, PriceServiceConnection } from '@pythnetwork/pyth-common-js'
import { argv } from 'process'

export class PriceServiceConnection2 extends PriceServiceConnection {
  public async getLatestVaasForIds (priceIds: HexString[]): Promise<Buffer[]> {
    const vaas = await this.getLatestVaas(priceIds)
    return vaas.map((v) => Buffer.from(v, 'base64'))
  }
}

(async () => {
  const PriceIds = [
    '08f781a893bc9340140c5f89c8a96f438bcfae4d1474cc0f688e3a52892c7318', // ALGO
    'f9c0172ba10dfa4d19088d94f5bf61d3b54d5bd7483a322a982e1373ee8ea31b', // BTC
    'ca80ba6dc32e08d06f1aa886011eed1d77c77be9eb761cc10d72b7d0a2fd57a6', // ETH
    '41f3625971ca2ed2263e78573fe5ce23e13d2558ed3f2e47ab0f84fb9e7ae722', // USDC
    '1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588', // USDT
    'bfaf7739cb6fe3e1c57a0ac08e1d931e9e6062d476fa57804e165ab572b5b621', // XRP
    // Equity.US.AI/USD
    'a36c0b485ebb9bbaf0d182d8208e7a2c2ae138e69f47712085d4166f1c847dbb',
    // Equity.US.AMC/USD
    'c21e81af5c80ee23c0b51c8b4f4ba0ea28c8b38bc85beb7b1335356a32023256',
    // Equity.US.AMGN/USD
    '2a424024e5a4438d4d698f99e25df39e347b3889f7249b64c771f7504a0d2f12',
    // Equity.US.AMZN/USD
    '095e126b86f4f416a21da0c44b997a379e8647514a1b78204ca0a6267801d00f',
    // Equity.US.ARKK/USD
    'fd4712eb77ed09b64d09b63cd86f8343af561730ce089d6cc5dd5320f2098be9',
    // Equity.US.AXP/USD
    '01f64be1849d432ddf6164c6bcf4ec8635db12aaa76132b2291561ffd6a29993',
    // Equity.US.BA/USD
    '40f63777ba678d5c2c7c69c4ad9daeb867d274bc785c5ada2c84b8613eeb5e14',
    // Equity.US.BLK/USD
    '9f8571f9844fb0987ee453ba743255fc26a28f25b0273f2ea708c2cc32c5d10b',
    // Equity.US.CAT/USD
    '6e03ddbdaf07cd975626dc72e567427ceaa05108f5ffa1611942cf4006cefb2c',
    // Equity.US.COIN/USD
    'a29b53fbc56604ef1f2b65e89e48b0f09bb77b3fb890f4c70ee8cbd68a12a94b',
    // Equity.US.CPNG/USD
    'c9606d7045eeb402289a7892cc57aa6087d8cbe3c6c195536f1aaf3f0e86801e',
    // Equity.US.CRM/USD
    '0d66aae904c7d457ed92c5d933e7d25ecb2b1e285b1be6a4e8520e38bc296161',
    // Equity.US.CSCO/USD
    'f1063ff9dea7f8052929e97e907218eff557542a59c54a60eb3a945b67759999'
  ]
  const conn = new PriceServiceConnection2('https://hermes-beta.pyth.network')
  const priceIds = PriceIds.slice(0, Number(argv[2]))
  console.log('Getting priceIds data for ', priceIds)
  const pythData = await conn.getLatestVaasForIds(priceIds)

  for (const data of pythData) {
    console.log(data.toString('hex'))
    console.log('LENGTH: ', data.toString('hex').length)
  }
})()
