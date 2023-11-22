"""
Pricecaster access class.
"""



from pyteal import (
    ABIReturnSubroutine,
    App,
    Assert,
    Concat,
    Expr,
    Extract,
    If,
    Int,
    Itob,
    ScratchVar,
    Seq,
    TealType,
    abi,
)

from contracts_unified.core.state_handler.global_handler import GlobalStateHandler
from contracts_unified.library.c3types import AppId, AssetId, InstrumentId, Price


class PricecasterEntry(abi.NamedTuple):
    """An entry from the pricecaster"""

    asa_id: abi.Field[AssetId]
    normalized_price: abi.Field[Price]
    price: abi.Field[abi.Uint64]
    confidence: abi.Field[abi.Uint64]
    exponent: abi.Field[abi.Uint32]
    price_ema: abi.Field[abi.Uint64]
    confidence_ema: abi.Field[abi.Uint64]
    attestation_time: abi.Field[abi.Uint64]
    publish_time: abi.Field[abi.Uint64]
    previous_publish_time: abi.Field[abi.Uint64]
    previous_price: abi.Field[abi.Uint64]
    previous_confidence: abi.Field[abi.Uint64]

def _get_key(page: Expr) -> Expr:
    return Extract(Itob(page), Int(7), Int(1))

@ABIReturnSubroutine
def get_normalized_price(instrument_id: InstrumentId, *, output: abi.Uint64) -> Expr:
    """Read data from the pricecaster"""

    entry_size = abi.make(PricecasterEntry).type_spec().byte_length_static()
    slot_size = 128 - 1

    entry = PricecasterEntry()
    pricecaster = AppId()
    ptr = abi.Uint64()
    start = abi.Uint64()
    end = abi.Uint64()
    data = ScratchVar(TealType.bytes)

    return Seq(
        # Get the pricecaster id
        pricecaster.set(GlobalStateHandler.get_pricecaster_id()),

        # Calculate base pointer of data in blob
        ptr.set(instrument_id.get() * Int(entry_size)),

        # Get start page
        start.set(ptr.get() / Int(slot_size)),

        # Get end page
        end.set((ptr.get() + Int(entry_size)) / Int(slot_size)),

        # Load first page of data
        page := App.globalGetEx(pricecaster.get(), _get_key(start.get())),
        Assert(page.hasValue()),
        data.store(page.value()),

        # Check for more data
        If(start.get() < end.get())
        .Then(
            page2 := App.globalGetEx(pricecaster.get(), _get_key(end.get())),
            Assert(page2.hasValue()),
            data.store(Concat(data.load(), page2.value())),
        ),

        # Extract entry
        entry.decode(Extract(data.load(), ptr.get() % Int(slot_size), Int(entry_size))),
        entry.normalized_price.store_into(output)
    )
