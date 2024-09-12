#!/usr/bin/python3
"""
================================================================================================

The Pricecaster Onchain Program

Version 10.0

(c) 2022-23 C3  LLC

------------------------------------------------------------------------------------------------

This program stores price data verified from Pyth price updates, which involves a VAA 
containing a merkle root and a Price Update containing a Merkle path to prove for data validity. 
To accept data, this application requires to be the last of a Wormhole VAA Verification
transaction group.

The payload format must be V4, see the README file for details.

------------------------------------------------------------------------------------------------

ASA ID mappings are stored off-chain in the backend system, so it's the responsibility of the
caller engine to mantain a canonical mapping between Pyth product-prices and ASA IDs.

The global state is treated like a linear array (Blob) of entries with the following format:

key             data
value           Linear array packed with fields as follow: 

                Bytes

                8               asa_id
                
                8               normalized price

                8               price
                8               confidence

                4               exponent

                8               price EMA
                8               confidence EMA

                8               publish time
                8               prev_publish_time

                24              reserved (all zero), for back compatibility


TOTAL           92 Bytes.

First byte of storage is reserved to keep number of entries.

* The coreid entry in the global state points to the deployed Wormhole core.

With this in mind, there is space for 127 * 63 bytes of space = 8001 bytes. 
As the last slot space is reserved for internal use and future expansion (SYSTEM_SLOT), there are 
8001/92 = 86   minus 1,  85 slots available for price storage.

The system slot layout is as follows:

Byte 
0           Last allocated slot.  
1           Config flags.
2..91       Reserved
------------------------------------------------------------------------------------------------
"""
from inspect import currentframe
from pyteal import *
from globalblob import *
from merkle import *
import sys

ALLOC_ASA_ID = Txn.application_args[1]
FLAGS_ARG = Txn.application_args[1]
SLOT_TEMP = ScratchVar(TealType.uint64)

SLOT_SIZE = 92
MAX_PRICE_SLOTS = int((63 * 127 / SLOT_SIZE) - 1)
FREE_ENTRY = Bytes('base16', '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000')
SYSTEM_SLOT_INDEX = Int(85)
SYSTEM_SLOT_OFFSET = SYSTEM_SLOT_INDEX * Int(SLOT_SIZE)

PRICE_CONF_EXP_BLOCK_OFFSET = Int(32)  # Starts after Price-id
PRICE_CONF_EXP_BLOCK_LENGTH = Int(20)

EMA_BLOCK_OFFSET = Int(68)
EMA_BLOCK_LENGTH = Int(16)

TIMESTAMP_BLOCK_OFFSET = Int(52)
TIMESTAMP_BLOCK_LENGTH = Int(16)
TIMESTAMP_SLOT_OFFSET = Int(52)

EXPONENT_OFFSET = PRICE_CONF_EXP_BLOCK_OFFSET + Int(8) + Int(8)

ASAID_SLOT_TUPLE_SIZE = Int(9)
UINT8_SIZE = Int(1)
UINT16_SIZE = Int(2)
UINT64_SIZE = Int(8)
UINT32_SIZE = Int(4)

ALGO_DECIMALS = Int(6)
PICO_DOLLARS_DECIMALS = Int(12)


CORE_OP_QUA = Bytes("CORE_OP_QUA")
OPERATOR_ADDRESS = Extract(App.globalGet(CORE_OP_QUA), Int(8), Int(32))
QUANT_ADDRESS = Extract(App.globalGet(CORE_OP_QUA), Int(40), Int(32))

def XAssert(cond, comment=None):
    return Assert(And(cond, Int(currentframe().f_back.f_lineno)), comment=comment)


@Subroutine(TealType.uint64)
def is_creator():
    return Txn.sender() == Global.creator_address()


@Subroutine(TealType.uint64)
def is_operator():
    return Txn.sender() == OPERATOR_ADDRESS


@Subroutine(TealType.uint64)
def is_quant_address():
    return Txn.sender() == QUANT_ADDRESS


@Subroutine(TealType.uint64)
def check_group_tx():
    #
    # Verifies that group contains expected transactions:
    #
    # - calls/optins issued with authorized appId (Wormhole Core).
    # - calls/optins issued for this appId (Pricecaster)
    # - payment transfers for upfront fees from owner.
    #
    # There must be at least one app call to Wormhole Core Id.
    #
    i = ScratchVar(TealType.uint64) 
    is_corecall = ScratchVar(TealType.uint64)
    wormhole_coreid = ScratchVar(TealType.uint64)
    return Seq([
        wormhole_coreid.store(ExtractUint64(App.globalGet(CORE_OP_QUA), Int(0))),
        is_corecall.store(Int(0)),
        For(i.store(Int(0)),
            i.load() < Global.group_size() - Int(1),
            i.store(i.load() + Int(1))).Do(Seq([
                If (Gtxn[i.load()].application_id() == wormhole_coreid.load(), is_corecall.store(Int(1))),
                Assert(
                    Or(
                        Gtxn[i.load()].application_id() == wormhole_coreid.load(),
                        Gtxn[i.load()].application_id() == Global.current_application_id(),
                        And(
                            Gtxn[i.load()].type_enum() == TxnType.Payment,
                            Gtxn[i.load()].sender() == OPERATOR_ADDRESS
                    )), comment="Invalid transaction in group")
                ])
        ),
        XAssert(Or(Tmpl.Int("TMPL_I_TESTING"), is_corecall.load() == Int(1)), comment="Must have a call to Wormhole Core"),
        Return(Int(1))
    ])


@Subroutine(TealType.uint64)
def get_entry_count():
    return GetByte(read_slot(SYSTEM_SLOT_INDEX), Int(0))


@Subroutine(TealType.none)
def inc_entry_count(prevCount):
    return GlobalBlob.write(SYSTEM_SLOT_INDEX * Int(SLOT_SIZE), Extract(Itob(prevCount + Int(1)), Int(7), Int(1)))


@Subroutine(TealType.bytes)
def read_slot(slot):
    return GlobalBlob.read(slot * Int(SLOT_SIZE), (slot + Int(1)) * Int(SLOT_SIZE))


@Subroutine(TealType.none)
def write_slot(slot, data):
    return Seq([
        XAssert(Len(data) == Int(SLOT_SIZE), comment="Packed price data must equal slot size"),
        XAssert(slot < get_entry_count(), comment="Slot must be allocated"),
        GlobalBlob.write(slot * Int(SLOT_SIZE), data),
    ])


@Subroutine(TealType.none)
def write_system_slot(data):
    return Seq(GlobalBlob.write(SYSTEM_SLOT_INDEX * Int(SLOT_SIZE), data))



@Subroutine(TealType.none)
def publish_data(asa_id, price_update_entry, slot):
    packed_price_data = ScratchVar(TealType.bytes)
    asa_decimals = ScratchVar(TealType.uint64)
    pyth_price = ScratchVar(TealType.uint64)
    normalized_price = ScratchVar(TealType.uint64)
    ad = AssetParam.decimals(asa_id)
    exponent = ScratchVar(TealType.uint64)
    norm_exp = Int(0xffffffff) & (Int(0x100000000) - exponent.load())

    return Seq([

        If (
            asa_id == Int(0), 

            # if Asset is 0 (ALGO), we cannot get decimals through AssetParams, so set to known value.
            asa_decimals.store(ALGO_DECIMALS),
            
            # otherwise, get onchain decimals parameter. 
            asa_decimals.store(Seq([ad, Assert(ad.hasValue()), ad.value()]))
            ),


        # Extract Pyth-price and exponent to normalize price

        pyth_price.store(Btoi(Extract(price_update_entry, PRICE_CONF_EXP_BLOCK_OFFSET, UINT64_SIZE))),
        exponent.store(Btoi(Extract(price_update_entry, EXPONENT_OFFSET, UINT32_SIZE))),

        # Normalize price as price * 10^(12 + exponent - asset_decimals) with  -12 <= exponent < 12,  0 <= d <= 19 
        #                                                  
        # Branch as follows, if exp < 0     p' = p * 10^12
        #                                     -----------------
        #                                       10^d * 10^ABS(e)
        #
        # otherwise,  p' = p * 10^12 * 10^e
        #                  -----------------
        #                        10^d
        #
        # where -12 <= e <= 12 ,  0 <= d <= 19
        #

        If (exponent.load() < Int(0x80000000),  # uint32, 2-compl positive 
            normalized_price.store(WideRatio([pyth_price.load(), Exp(Int(10), PICO_DOLLARS_DECIMALS), Exp(Int(10), exponent.load())], 
                                                [Exp(Int(10), asa_decimals.load())])),

            normalized_price.store(WideRatio([pyth_price.load(), Exp(Int(10), PICO_DOLLARS_DECIMALS)], 
                                                [Exp(Int(10), asa_decimals.load()), Exp(Int(10), norm_exp)]))
        ),

        # Concatenate all
        packed_price_data.store(Concat(
            Itob(asa_id),  # 8 bytes
            Itob(normalized_price.load()), # 8 bytes
            Extract(price_update_entry, PRICE_CONF_EXP_BLOCK_OFFSET, PRICE_CONF_EXP_BLOCK_LENGTH),   # price, confidence, exponent  8+8+4 = 20 bytes
            Extract(price_update_entry, EMA_BLOCK_OFFSET, EMA_BLOCK_LENGTH), # price EMA,  confidence EMA  8+8 = 16 bytes
            Extract(price_update_entry, TIMESTAMP_BLOCK_OFFSET, TIMESTAMP_BLOCK_LENGTH),   # pub_time,prev_pub_time 8+8 = 16 bytes
            Bytes("base16", "000000000000000000000000000000000000000000000000") # reserved, zero-fill, 24 bytes
        )),

        # If normalized price is 0, do not update slot but log event so
        # further analysis can be done if required.

        If (normalized_price.load() == Int(0)).Then(Seq(
            Log(Concat(Bytes("NORM_PRICE_ZERO@"), Itob(slot), packed_price_data.load())),
            Return()
        )),

        # Update blob entry

        write_slot(slot, packed_price_data.load()),
        Log(Concat(Bytes('STORE@'), Itob(slot), packed_price_data.load()))
    ])


def store():
    """
    Commits a store transaction.

    * Sender must be owner
    * This must be part of a transaction group
    * All calls in group must be issued from authorized Wormhole core.
    * Argument 0 is 'store'
    * Argument 1 is a 20-byte array containing the merkle root read from the Wormhole VAA
    * Argument 2 must be array of ASA IDs corresponding to each of the attestations.
    * Argument 3 must be Price Update payload. This can exceed the argument size limits by using the Txn note field.
    * Argument 4 must be Total Computation Budget to provide.

    """
    MERKLE_ROOT = Txn.application_args[1]
    ASAID_SLOT_ARRAY = Txn.application_args[2]
    PRICE_UPDATES_DATA_ARG = Txn.application_args[3]
    PRICE_UPDATE_BUDGET = Txn.application_args[4]
    PRICE_UPDATES_DATA_EXT = Txn.note()
    price_updates_data = ScratchVar(TealType.bytes)
    price_update_count = ScratchVar(TealType.uint64)
    price_update_size = ScratchVar(TealType.uint64)
    price_update_entry = ScratchVar(TealType.bytes)
    merkle_path_node_count = ScratchVar(TealType.uint64)
    merkle_path = ScratchVar(TealType.bytes)
    cursor = ScratchVar(TealType.uint64)
    asa_id = ScratchVar(TealType.uint64)
    slot = ScratchVar(TealType.uint64)
    slot_data = ScratchVar(TealType.bytes)

    i = ScratchVar(TealType.uint64)
    op_pool = OpUp(OpUpMode.OnCall)

    return Seq(
        XAssert(is_operator(), comment="Must be operator to call store"),

        XAssert(Len(MERKLE_ROOT) == MERKLE_HASH_SIZE, comment="Merkle root must be 20 bytes"),
        
        # If testing mode is active, ignore group checks
        XAssert(Or(Tmpl.Int("TMPL_I_TESTING"), Global.group_size() > Int(1)), comment="Must be part of a group transaction"),
        XAssert(Txn.application_args.length() == Int(5), comment="Store call must have 4 arguments"),
        XAssert(Or(Tmpl.Int("TMPL_I_TESTING"), check_group_tx())),

        # Verify that we have an array of (Uint64) values
        XAssert((Len(ASAID_SLOT_ARRAY) % ASAID_SLOT_TUPLE_SIZE) == Int(0), comment="ASA ID array must be multiple of tuple-size"),

        # Store all price update data, including extended data in Note field.
        price_updates_data.store(Concat(PRICE_UPDATES_DATA_ARG, PRICE_UPDATES_DATA_EXT)),
        
        # get price update count
        price_update_count.store(GetByte(price_updates_data.load(), Int(0))),

        # must be one ASA ID for each price update
        XAssert(Len(ASAID_SLOT_ARRAY) == ASAID_SLOT_TUPLE_SIZE * price_update_count.load(), comment="Must have one ASA ID for each price update"),

        # Read each price update, verify merkle proof, store in global state.
        # Use each ASA IDs  passed in call.

        cursor.store(Int(1)), # Skip update entry count

        op_pool.ensure_budget(Btoi(PRICE_UPDATE_BUDGET)),
        For(i.store(Int(0)), i.load() < price_update_count.load(), i.store(i.load() + Int(1))).Do(
            Seq(
                asa_id.store(ExtractUint64(ASAID_SLOT_ARRAY, i.load() * ASAID_SLOT_TUPLE_SIZE)),

                # Extract price Update
                price_update_size.store(ExtractUint16(price_updates_data.load(), cursor.load())),

                cursor.store(cursor.load() + UINT16_SIZE), 

                # Load price update 
                price_update_entry.store(Extract(price_updates_data.load(), cursor.load(), price_update_size.load())),

                ## Extract merkle path information

                cursor.store(cursor.load() + price_update_size.load()),
                merkle_path_node_count.store(GetByte(price_updates_data.load(), cursor.load())),
                cursor.store(cursor.load() + Int(1)),
                merkle_path.store(Extract(price_updates_data.load(), cursor.load(), merkle_path_node_count.load() * MERKLE_HASH_SIZE)),

                ## Slot must be allocated already for this ASA
                
                slot.store(GetByte(ASAID_SLOT_ARRAY, i.load() * ASAID_SLOT_TUPLE_SIZE + UINT64_SIZE)),
                slot_data.store(read_slot(slot.load())),
                XAssert(ExtractUint64(slot_data.load(), Int(0)) == asa_id.load(), comment="Slot must be allocated for this ASA"),

                ## Verify merkle proof
                XAssert(Or(Tmpl.Int("TMPL_I_DISABLE_MERKLE_PROOF"), 
                        merkle_proof_verify(price_update_entry.load(), 
                                            merkle_path.load(), 
                                            merkle_path_node_count.load(), 
                                            MERKLE_ROOT)), comment="Merkle proof failed"),
                
                # Chop off enum marker (00) in the price entry
                price_update_entry.store(Suffix(price_update_entry.load(), Int(1))),

                # If an update has an older timestamp must be ignored.
                If(ExtractUint64(slot_data.load(), TIMESTAMP_SLOT_OFFSET) > ExtractUint64(price_update_entry.load(), TIMESTAMP_BLOCK_OFFSET),
                    Seq(
                        Log(Concat(Bytes("PRICE_IGNORED_OLD@"), Itob(asa_id.load()))), 
                        Continue()
                        )
                    ),  

                # Execute publication

                publish_data(asa_id.load(), price_update_entry.load(), slot.load()),

                # Advance to next item
                cursor.store(cursor.load() + (merkle_path_node_count.load() * MERKLE_HASH_SIZE)),
                )
        ),
        Approve())


def alloc_new_slot():
    #
    # Allocates a new slot for a particular ASA. Can be done only by QUANT ADDRESS
    # Argument 1 must be ASA identifier.
    #
    entryCount = ScratchVar(TealType.uint64)
    return Seq([
        XAssert(is_quant_address(), comment="must be quant address to call alloc"),
        entryCount.store(get_entry_count()),
        XAssert(entryCount.load() <= Int(MAX_PRICE_SLOTS), comment="Global state full"),
        inc_entry_count(entryCount.load()),
        write_slot(entryCount.load(), Replace(FREE_ENTRY, Int(0), ALLOC_ASA_ID)),
        Log(Concat(Bytes("ALLOC@"), Itob(entryCount.load()))),
        Approve()
    ])


def reset(): 
    #
    # Resets all contract info to zero
    #
    op_pool = OpUp(OpUpMode.OnCall)
    sys_flag = ScratchVar(TealType.uint64)
    return Seq([
        XAssert(is_creator(), comment="Must be owner to call reset"),
        op_pool.maximize_budget(Int(2000)),
        sys_flag.store(GetByte(read_slot(SYSTEM_SLOT_INDEX), Int(1))),
        GlobalBlob.zero(),
        GlobalBlob.set_byte(SYSTEM_SLOT_INDEX * Int(SLOT_SIZE) + Int(1), sys_flag.load()),
        Approve()
    ])


@Subroutine(TealType.none)
def set_sys_flag(flag):
    sys_slot = ScratchVar(TealType.bytes)
    return Seq(
        sys_slot.store(SetByte(read_slot(SYSTEM_SLOT_INDEX), Int(1), flag & Int(0xFF))),
        write_system_slot(sys_slot.load()),
    )


def set_flags():
    #
    # Sets configuration flags 
    #
    return Seq(
        XAssert(is_creator(), comment="Must be owner to call setflags"),
        # mask-out the readonly flags n bootstrap call
        set_sys_flag(Int(0b00111111) & Btoi(FLAGS_ARG)),
        Approve()
    )


def nop():
    return Seq(
        Approve()
    )


@Subroutine(TealType.uint64)
# Arg0: Bootstrap with the authorized VAA Processor appid.
# Arg1: Operator address.
# Arg2: Quant address.
def bootstrap():
    op_pool = OpUp(OpUpMode.OnCall)
    return Seq(
        op_pool.maximize_budget(Int(2000)),
        Assert(Len(Txn.application_args[0]) == Int(8)),
        Assert(Len(Txn.application_args[1]) == Int(32)),
        Assert(Len(Txn.application_args[2]) == Int(32)),
        App.globalPut(CORE_OP_QUA, Concat(Txn.application_args[0], Txn.application_args[1], Txn.application_args[2])),
        GlobalBlob.zero(),

        # Enable flags
        set_sys_flag( Tmpl.Int("TMPL_I_TESTING") + Tmpl.Int("TMPL_I_DISABLE_MERKLE_PROOF") ),
        Approve()
    )


def pricecaster_program():

    METHOD = Txn.application_args[0]

    handle_create = Return(bootstrap())
    handle_update = Return(is_creator())
    handle_delete = Return(is_creator())
    handle_optin = Return(Int(1))
    handle_noop = Cond(
        [METHOD == MethodSignature("nop()void"), nop()],
        [METHOD == Bytes("store"), store()],
        [METHOD == Bytes("alloc"), alloc_new_slot()],
        [METHOD == Bytes("reset"), reset()],
        [METHOD == Bytes("setflags"), set_flags()]
    )
    return Seq([
        # XAssert(Txn.rekey_to() == Global.zero_address()),
        Assert(Txn.asset_close_to() == Global.zero_address(), comment="Asset close to must be zero"),
        Assert(Txn.close_remainder_to() == Global.zero_address(), comment="Close remainder to must be zero"),
        Cond(
        [Txn.application_id() == Int(0), handle_create],
        [Txn.on_completion() == OnComplete.OptIn, handle_optin],
        [Txn.on_completion() == OnComplete.UpdateApplication, handle_update],
        [Txn.on_completion() == OnComplete.DeleteApplication, handle_delete],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop])
    ])


def clear_state_program():
    return Int(1)


if __name__ == "__main__":

    approval_outfile = "teal/build/pricecaster-approval.teal"
    clear_state_outfile = "teal/build/pricecaster-clear.teal"

    if len(sys.argv) >= 2:
        approval_outfile = sys.argv[1]

    if len(sys.argv) >= 3:
        clear_state_outfile = sys.argv[2]

    print("Pricecaster TEAL Program     Version 10.0, (c) 2022-23 C3")
    print("Compiling approval program...")

    optimize_options = OptimizeOptions(scratch_slots=True)

    with open(approval_outfile, "w") as f:
        compiled = compileTeal(pricecaster_program(),
                               mode=Mode.Application, version=9, assembleConstants=True, optimize=optimize_options)
        f.write(compiled)

    print("Written to " + approval_outfile)
    print("Compiling clear state program...")

    with open(clear_state_outfile, "w") as f:
        compiled = compileTeal(clear_state_program(),
                               mode=Mode.Application, version=9)
        f.write(compiled)

    print("Written to " + clear_state_outfile)
