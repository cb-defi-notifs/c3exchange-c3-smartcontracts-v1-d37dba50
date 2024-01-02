# CCTP Support Subsystem 

## Overview

The CCTP Hub This subsystem is responsible for providing the base infrastructure necessary for deposit and withdrawals of Circle USDC using the CCTP protocol for minting/burning to/from C3 Services.

This directory contains the CCTP Hub contract and the associated build & deployment scripts to be used with Hardhat/Ignition.

## Deployment

Use `npm i` to install all development dependencies and tools.

Compile the contracts with

```
npx hardhat compile
```

You can deploy using Ignition with private keys using:

```
# For Testnet Avalanche (Fuji)
NETWORK=TESTNET AUTH_C3_APPID=<app-id> FUJI_INFURA_API_KEY=... FUJI_DEPLOYMENT_PK=... npx hardhat ignition deploy ignition/modules/cctpHub.ts --network fuji
```



### Ledger Deployment

You can deploy TESTNET  / MAINNET contracts using Ledger hardware wallet using the `scripts/deploy-ledger.js` script by running:

```
npx hardhat run --network <fuji | avalanche> scripts/deploy-ledger.ts
```

The following environment variables are needed:

* `AUTH_C3_APPID` - The C3 App ID authorized as withdraw origins or deposit destination of USDCs.
* `FUJI_INFURA_API_KEY` - The Infura API key for the Fuji or Avalanche network.
* `LEDGER_ACCOUNT` - The Ledger account to use for deployment.

## Change appID

To change the appID of the CCTP Hub, you can use the `scripts/set-appid.ts` script by running:

```
npx hardhat run --network <fuji | avalanche> scripts/set-appid.ts

```

The following environment variables are needed:

* `AUTH_C3_APPID` - The new  C3 App ID authorized as withdraw origins or deposit destination of USDCs.
* `HUB_ADDRESS` - The deployed hub address to call the AppId change operation.
* `LEDGER_ACCOUNT` - The Ledger account to use for deployment.

## Run tests

Run the contract tests with:

```
npx hardhat test
```

Perform coverage analysis with:

```
npx hardhat coverage
```

Perform gas analysis with:

```
REPORT_GAS=true npx hardhat test
```

