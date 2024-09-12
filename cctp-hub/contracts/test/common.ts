import { Account, AssetId, InstrumentAmount } from "@c3exchange/sdk"

export async function getAccountC3Balance(accountSdk: Account, assetId: AssetId): Promise<InstrumentAmount> {
    const balance = await accountSdk.getBalance()
    const assetAmount = balance.instrumentsInfo.find((info) => info.cash.instrument.asaId === assetId)
    if (assetAmount === undefined) {
        throw new Error("Asset not found")
    }
    return assetAmount.cash
}

export async function sleep(ms: number) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export function bigIntToBytes(bi: bigint | number, size: number) {
    let hex = bi.toString(16);
    // Pad the hex with zeros so it matches the size in bytes
    if (hex.length !== size * 2) {
      hex = hex.padStart(size * 2, '0');
    }
    const byteArray = new Uint8Array(hex.length / 2);
    for (let i = 0, j = 0; i < hex.length / 2; i++, j += 2) {
      byteArray[i] = parseInt(hex.slice(j, j + 2), 16);
    }
    return byteArray;
  }
