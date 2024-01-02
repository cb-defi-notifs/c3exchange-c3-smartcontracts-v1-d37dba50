import { getPythClusterApiUrl, getPythProgramKeyForCluster, parseProductData } from '@pythnetwork/client'
import { Cluster, Connection } from '@solana/web3.js'
const columnify = require('columnify')

type PythCluster = Cluster | 'pythtest-conformance' | 'pythnet' | 'localnet' | 'pythtest-crosschain'

(async () => {
  const pythClusterName = process.argv[2] as PythCluster
  if (!pythClusterName) {
    console.error('Missing cluster name, usage dump-priceids.ts <cluster> \n\nwhere cluster is one of: pythtest-conformance, pythnet, localnet, pythtest-crosschain')
    return
  }

  const PythClusterName: PythCluster = 'pythnet'
  const connection = new Connection(getPythClusterApiUrl(PythClusterName))
  const accounts = await connection.getProgramAccounts(getPythProgramKeyForCluster(PythClusterName), 'finalized')

  type PriceEntry = {
    symbol: string,
    priceId: string
  }

  const priceEntryData: PriceEntry[] = []

  for (const acc of accounts) {
    const productData = parseProductData(acc.account.data)
    if (productData.type === 2 && productData.product.symbol) {
      if (productData.priceAccountKey) {
        priceEntryData.push({ symbol: productData.product.symbol, priceId: Buffer.from(productData.priceAccountKey.toBytes()).toString('hex') })
      } else {
        priceEntryData.push({ symbol: productData.product.symbol, priceId: 'N/A' })
      }
    }
  }

  console.log(columnify(priceEntryData.sort((a, b) => a.symbol > b.symbol ? 1 : -1)))
})()
