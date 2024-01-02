module.exports = {
  sources: {
    pricecaster_pyteal: 'teal/pyteal/pricecaster-v2.py'
  },
  networks: {
    testnet: {
      token: '',
      api: 'https://node.testnet.algoexplorerapi.io',
      port: ''
    },
    mainnet: {
      token: '',
      api: 'https://api.algoexplorer.io',
      port: ''
    },
    betanet: {
      token: '',
      api: 'https://api.betanet.algoexplorer.io',
      port: ''
    },
    dev: {
      token: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      api: 'http://localhost',
      port: '4001'
    }
  }
}
