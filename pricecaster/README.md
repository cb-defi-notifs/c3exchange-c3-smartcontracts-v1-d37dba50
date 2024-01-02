
# Pricecaster Contract

## Introduction

This directory contains the set of contracts for the Pricecaster service, which comprises on-chain and off-chain components and tools. The purpose is to consume prices from "price fetchers" and feed blockchain publishers. In particular, this system is tailored at C3 Specific needs; in that regard, the current implementation is a Pyth Price Service client that is used to get Price Updates from the "Hermes" Pyth system and feed the payload and cryptographic verification data to a transaction group for validation. Subsequently, the data is processed and stored in the Pricecaster app contract, which is deployed on the Algorand blockchain. For details regarding Wormhole VAAs see design documents: 

  https://github.com/wormhole-foundation/wormhole/tree/main/whitepapers

## System Overview

A generic diagram of how the system works is shown below:

![System Overview Diagram](doc/systemoverview.png)

The Pyth Network is constantly generating aggregated price data from a set of trusted providers. An endpoint is offered by the Price Service (Hermes) from where Pricecaster backend polls for a set of price updates; the Pyth system will generate a price update dataset along with a Merkle Tree root to proof for each data item inclusion. To secure this proof, it is sent to the Wormhole network where a set of guardians will sign the data and generate a VAA (Verifiable Attestation). This VAA plus the Price Update Data set is sent to the Pricecaster backend, which will submit to the Pricecontract for verification and storage.

### Wormhole Core Contracts

The verification of each received VAA is done by the tandem of Wormhole SDK plus core Wormhole contracts deployed in Algorand chain. Refer to https://github.com/wormhole-foundation/wormhole/tree/main/algorand for the Wormhole Token and Core Bridge components, and to https://github.com/wormhole-foundation/wormhole/tree/main/sdk/js for the JS SDK.

The backend will currently **call the Pricecaster contract to store data** as the last TX group. See below for details on how Pricecaster works.

## Prerequisites

The pricecaster system requires the following components to run:

* Algorand node.
* Optional C3 API Server where Pricecaster will obtain the App Id, and in consecuence, current slot Layout.  For Slot Layout organization see sections ahead.  The AppID can be overriden with a special environment setting.
* **Pyth Price Service**. Pyth network offers the public endpoint ```https://hermes-beta.pyth.network```.  This is enough for development and non-production deployments; for production Pyth recommends a dedicated installation. See https://github.com/pyth-network/pyth-crosschain/tree/main/third_party/pyth/price-service.  Note that a dedicated installation **also requires a Wormhole spy deployment**. 

* Deployed Wormhole contracts 

For local development the recommendation is to use **Tilt** to run: an Algorand sandbox with deployed Wormhole contracts, a set of guardians and Wormhole daemon, ready to be used.  This is hard to deploy by-hand, you have been warned.

To use Tilt, 

* Install Docker + Kubernetes Support.  The straightforward way is to use Docker Desktop and activate Kubernetes Support, both in Linux MacOS or Windows.
* Install https://docs.tilt.dev/install.html.  Tilt can be installed under WSL.
* Clone the Wormhole repository from  https://github.com/wormhole-foundation/wormhole.
* Under this directory run

  ```
  tilt up -- --algorand
  ```

  The live Wormhole network runs 19 guardians, so to simulate more realistic conditions, set the number of guardians > 1 using the --num parameter.

* Use the Tilt console to check for all services to be ready.  Note that the Algorand sandbox will have several pre-made and pre-funded accounts with vanity-addresses prefixed by `DEV...`  Use those accounts for development only!

## Pricecaster Onchain App Storage

The Pricecaster Smart Contract mantains a global space of storage with a layout of logical slots that are sequentially added as required. The global space key/value entries are stored as follows:

| key | value |
|-----|-------|
| coreid | The Wormhole Core application id to validate VAAs |
| 0x00   | Linear space, bytes 0..127 |
| 0x01   | Linear space, bytes 128..255 |
| 0x02   | Linear space, bytes 256..383 |
| .    | .                          |
| .    | .                          |
| .    | .                          |
| 0x3e | Linear space, bytes 7874..8001   |

The linear space offers up to 8kB, each slot is 92 bytes wide (see format further below); so 86 slots are available. Actually 85 slots are available to store price information, as the slot with index 85 is the **system slot** which is used for internal data' bookkeeping. So the entire linear space is logically divided as:

| Slot 0 | Slot 1 | ... | Slot 84 | System Slot |

### System Slot

The system slot has the following organization:

| Field | Explanation | Size (bytes) |
|-------|-------------|--------------|
| Entry count | The number of allocated slots | 1 |
| Config flags | A set of configuration flags. See below | 1 |
| Reserved |  Reserved for future use | 90 |


#### Configuration flags

The **setflags** app call is used by the operator to change operating flags. This field is a 8-bit number with the following meaning:

```
7 6 5 4 3 2 1 0
+ + + + + + + + 
| | | | | | | +-------- Reserved
| | | | | | +---------- Reserved
| | | | | +------------ Reserved
| | | | +-------------- Reserved
| | | +---------------- Reserved
| | +------------------ Reserved
| +-------------------- System Use (Disable Merkle Proof Verification)
+---------------------- System Use (Testing-mode deployment)
```

Bits 7 and 6 are set by system at contract bootstraping stage and cannot be set by operator.

### Price slots

Price slots have the following format:

| Field         | Explanation | Size (bytes) |
|---------------|-------------|--------------|
| ASA ID        | The Algorand Standard Asset (ASA) identifier for this price | 8 |
| Norm_Price    | The C3-Normalized price. See details below. | 8            |
| Price         | The price as integer.  Use the `exponent` field as `price` * 10^`exponent` to obtain decimal value. | 8            |
| Confidence    | The confidence (standard deviation) of the price | 8            |
| Exponent      | The exponent to convert integer to decimal values | 4            | 
| Price EMA     | The exponential-median-average (EMA) of the price field over a 30-day period | 8 | 
| Confidence EMA| The exponential-median-average (EMA) of the confidence field over a 30-day period | 8 | 
| Publish Time | The timestamp of the moment the price was published in the Pyth Network | 8 |
| Prev Publish Time | The previous known Publish Time for this asset | 8 |
| Reserved          | Space reserved for future extension | 24 |

A slot is allocated using the **alloc** app call. A slot allocation operation sets the ASA ID for which prices will be stored in the slot. Also this extends the number of valid slots by 1,  increasing the _entry count_ field in the **System Slot**.

### Price storage formats

As is shown in the table above, prices are reported in two-formats:

* **Standard price**  This is the original price in the Pyth payload.  To obtain the real value you must use `exponent` field to set the decimal point as  `p' = p * 10^e` 
* **C3-Normalized price** This is the price in terms of _picodollars per microunit_, and is targeted at C3 centric applications. The normalization is calculated as `p' = p*10^(12+e-d)` where `e` is the exponent and `d` the number of decimals the asset uses.  `d` is obtained by looking at ASA parameter `Decimals`.

### Exponent and Decimal Ranges

Pyth network exponents are at time of this writing in the range `e=[-8,8]` but future expansions can raise this to `e=[-12,12]`.  Decimals according to Algorand can be from zero (indivisible ASA) to 19.
With this in mind, the normalized price format will yield the following values with boundary `d` and `e` values:

| d | e | Result |
|---|---|--------|
|0  |-12| p' = p | 
|0  |12 | p' = p*10^24 (Overflow). The maximum exponent usable with 0 decimals is +7. |
|19 |-12| p' = p/10^19 =~ 0 |
|19 |12 | p' = p*10^5 |
|0  |0  | p' = p*10^12|
|19 |0  | p' = 0| 

### Accounts 

The Pricecaster/C3 system operates with three accounts:

* Creator:  The account that deploys and updates the contract bytecode to/in the Algorand chain. This account also performs privileged operations such as **reset**, **setflags** et al.
* Operator: The account that issues the **store** app call to the Pricecaster contract.
* Quant: The account that issues the **alloc** app call to the Pricecaster contract.

### Store operation

The Pricecaster app will allow storage to succeed only if the transaction group contains:

* Sender is the contract OPERATOR account.
* Calls/optins issued with authorized appId (Wormhole Core).
* Calls/optins issued for the Pricecaster appid.
* Payment transfers for upfront fees from OPERATOR.
* There must be at least one app call to Wormhole Core Id.

For normalized price calculation, the onchain ASA information is retrieved for the number of decimals. The exception is the ASA ID 0 which is used for **ALGO** with hardcoded 6 (six) decimals.

A successful store operation will perform one of the following:

* Publish data and log `STORE@NN...` where `NN` is the slot number, followed by the 92-byte-sized slot data.
* If the Normalized Price is zero (0), log `NORM_PRICE_ZERO@NN..` where `NN` is the slot number, followed by the 92-byte-sized slot data, _and skip data publication_
* If the timestamp of the new price is older than the stored in the slot, log `PRICE_IGNORED_OLD@NN` where `NN` is the slot number, _and skip data publication_


### Reset operation

The linear space can be zeroed, thus deallocating all slots and resetting the entry count to 0, by calling the privileged operation **reset**.

## Operation cost

This Pricecaster system has a limit of 8 price updates per transaction group (VAA verification + store operation) due to
foreign reference limitations.

The cost of operation is defined by the following formula:

Let $T_C$ be the transaction group cost, $n$ the number of prices to publish, $V_F$ the VAA verification fee, $B_F$ the base store operation fee, $P_F$ the fee per additional published price, then:

$T_C = \lceil \frac{n}{8} \rceil(V_F +  B_F) + P_F(n - \lceil \frac{n}{8} \rceil)$

Where for the current version constants are:

$V_F = 0.002$ $B_F = 0.004$ $P_F = 0.0035$

As a practical calculation lets suppose we have 30 assets.  Each transaction group execution will cost:

$T_C = \lceil \frac{30}{8} \rceil(0.002 + 0.004) + 0.0035(30 - \lceil \frac{30}{8} \rceil) = 0.024 + 0.0035(30 - 4) = 0.024 + 0.0035(26) = 0.024 + 0.091 = 0.115$ ALGO

 For publishing price data update on each block we need ~19 publications per minute, this yields 2.185 ALGOs per minute, or 131 ALGOs per hour, or 3144 ALGOs per day. 

## Monthly budget based on publication interval

Following the above formula, the monthly budget $M_B$ for publishing $N$ assets with a publication frequency $F$ in milliseconds (`PYTH_PRICESERVICE_POLL_INTERVAL` setting) is:

$M_B(N,F) = T_C \times \frac { 60 \times 60 \times 24 \times 30 \times 1000} {F}$

## Tests

The tests are designed to run under **Tilt** environment.   See the Prerequisites section above on how to setup Tilt.

Run the Pricecaster contract tests with:

```
npm run test-sc
```

## Additional tools

The following tools are available to help development:

* `tools/dump-priceids.ts`:  Execute with `npx ts-node`  to dump all available products/assets available in Pyth with it's corresponding Price Id. The default behavior is to dump `devnet` prices, change to `mainnet-beta` if you want.
* `tools/pcasmon.ts`: Tool to monitor the Pricecaster onchain contents. Execute it with the `appId` and `network` options.

## Appendix

### VAA Structure

VAA structure is defined in: 
 https://github.com/certusone/wormhole/blob/dev.v2/whitepapers/0001_generic_message_passing.md

 Governance VAAs:
 https://github.com/certusone/wormhole/blob/dev.v2/whitepapers/0002_governance_messaging.md

 Sample Ethereum Struct Reference: 
 https://github.com/certusone/wormhole/blob/dev.v2/ethereum/contracts/Structs.sol

```
 VAA
 i Bytes        Field   
 0 1            Version
 1 4            GuardianSetIndex
 5 1            LenSignatures (LN)
 6 66*LN        Signatures where each S = { guardianIndex (1),r(32),s(32),v(1) }
 -------------------------------------< hashed/signed body starts here.
 4            timestamp
 4            Nonce
 2            emitterChainId
 32           emitterAddress
 8            sequence
 1            consistencyLevel
 N            payload
 --------------------------------------< hashed/signed body ends here.
```

### Sample Pyth Price Update

```
504e4155     header   'PNAU'
01           major version (1)
00           minor version (0)
00           Vector of bytes,  reserved for future extension
00           type-indicator (WormholeMerkle)
00a0         Length of VAA in bytes (160)

--------- VAA with Merkle root ----------------------------------------------------------------------------

01
00000000
01           # signatures
00a65271a4d81be2e825f4b77b95576ef5f368009a91cf4ed6cf21b08b6f0bdfc575d55a3a628165ce81e41b9e3406d3dee8b169390b0f4559b8b099d4f7ed57cd01  sig

64ba51ac                                                          timestamp
00000000                                                          nonce
001a                                                              emitterChainId (PythNet=26)
e101faedac5851e32b9b23b5f9411a8c2bac4aae3ed4dd7b811dd1a72ea4aa71  emitterAddress
0000000000b1ec49                                                  sequence
01                                                                consistency

vaa Payload follows:

41555756                                    Header AUWV
00                                          WormholeMerkleRoot enum marker
00000000050d5893                            merkle_root  (Slot)
00002710                                    merkle_root  (ring_size)
1900ae58deedf1d45e6fedc738fa256a12f2b25a    merkle root hash)

-----------------------------------------------------------------------------------------------------------

priceUpdates follow:

05                                          length of Vec<MerklePriceUpdate>  (5)
0055                                        length of data that follows (85 bytes)
00                                          type: PriceUpdate/Message enum
08f781a893bc9340140c5f89c8a96f438bcfae4d1474cc0f688e3a52892c7318        price-id
0000000000ae53e4                                                        price
00000000000014a9                                                        conf
fffffff8                                                                exponent
0000000064ba51ac                                                        publish_time
0000000064ba51aa                                                        prev_publish_time
0000000000ae8977                                                        ema_price
0000000000001686                                                        ema_conf

09 number of MarklePath entries 

ce4c7053b9853633d5a99a1072d55a9492c614bd
6d2b15d18335c7baa153531dce377363a4a5f912
0fc764d73e47f8fae3728689b201e83c61e54467
5fb1b9f7f2e63b6b5963eea3485a348746e9b4ee
f30070728546556a187abed30b3154c33b23eae2
e9788029f2622a372e8156220c3e386bee980138
be28705a69bb9b129a50ba22af331929b40dd2c8
6ab0cc5128c8f5a1c5cf7e0622f492363a5ad81c
9066a91f4aaf6877b54117947dd2f73f63446a77

.
.
.


```

## License

Copyright 2022, 2023 C3. 

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.


