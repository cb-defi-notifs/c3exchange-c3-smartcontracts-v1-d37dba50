"""User proxy stateless contract for C3"""

from typing import cast

from pyteal import (
    ABIReturnSubroutine,
    And,
    Approve,
    Assert,
    Base64Decode,
    Btoi,
    Bytes,
    Concat,
    Cond,
    EcdsaCurve,
    EcdsaRecover,
    Ed25519Verify_Bare,
    Expr,
    Extract,
    For,
    Global,
    Gtxn,
    If,
    Int,
    Keccak256,
    OnComplete,
    Or,
    ScratchVar,
    Seq,
    Substring,
    TealType,
    Tmpl,
    Txn,
    TxnType,
    abi,
)

from contracts_unified.library.c3types_user import (
    AbiOperationId,
    DelegationData,
    OperationId,
    OperationMetaData,
    SignedHeader,
    SigningMethod,
)

ETHEREUM_ADDRESS_START = Int(12)
ETHEREUM_ADDRESS_END = Int(32)


class UserProxyStaticData(abi.NamedTuple):
    """Static data for the user proxy contract"""
    # (address)
    server : abi.Field[abi.Address]  # 32 bytes


@ABIReturnSubroutine
def verify_signature(
    signer: abi.Address,
    metadata: OperationMetaData,
) -> Expr:
    """Verify the signature of the signed data against the given signer"""

    verify_input = abi.DynamicBytes()
    header_data = abi.DynamicBytes()
    op_data = abi.DynamicBytes()
    data_prefix = abi.DynamicBytes()
    signature = abi.DynamicBytes()
    signature_method = abi.Uint8()
    encoded_data = abi.DynamicBytes()

    return Seq(
        # Decode and extract the signed data
        metadata.header.use(lambda data: header_data.set(data.encode())),
        metadata.operation.store_into(op_data),
        metadata.encoded_signed_data.store_into(encoded_data),
        metadata.data_prefix.store_into(data_prefix),
        metadata.signature.store_into(signature),
        metadata.signature_method.store_into(signature_method),

        # Prepend the given data prefix to the data
        verify_input.set(Concat(data_prefix.get(), encoded_data.get())),
        # Check that the encoded Base64 data matches
        Assert(Concat(Bytes("(C3.IO)0"), header_data.get(), op_data.get()) == Base64Decode.std(encoded_data.get())),

        # Switch on the signature method
        Cond(
            [signature_method.get() == SigningMethod.Ed25519, Seq(
                Assert(Ed25519Verify_Bare(verify_input.get(), signature.get(), signer.get()))
            )],
            [signature_method.get() == SigningMethod.EcdsaSecp256k1, Seq(
                EcdsaRecover(
                    EcdsaCurve.Secp256k1,
                    Keccak256(verify_input.get()),
                    # V: Convert from Ethereum recovery-ids 27/28 to standardized 0/1
                    (Btoi(Extract(signature.get(), Int(64), Int(1)))) - Int(27),
                    # R
                    Extract(signature.get(), Int(0), Int(32)),
                    # S
                    Extract(signature.get(), Int(32), Int(32))
                ).outputReducer(lambda rec_pk_x,
                    # TODO: Extract signer length and compare only those bytes to remove ethereum start and end
                    rec_pk_y: Assert(Substring(signer.get(), ETHEREUM_ADDRESS_START, ETHEREUM_ADDRESS_END) ==
                        Substring(Keccak256(Concat(rec_pk_x, rec_pk_y)), ETHEREUM_ADDRESS_START, ETHEREUM_ADDRESS_END)
                    )
                )
            )],
        ),
    )


@ABIReturnSubroutine
def verify_signatures(target: abi.Address, encoded_delegation, ticket: OperationMetaData):
    """Verify the ticket signature and the delegation signature chain"""

    # Signers used to validate the delegation chain
    current_signer = abi.make(abi.Address)
    data_signer = abi.make(abi.Address)

    # Operation code of delegation data
    operation = AbiOperationId()

    # FIXME: Give these types some names and comments
    delegation_list = abi.make(abi.DynamicArray[OperationMetaData])
    current_signed_data = OperationMetaData()
    delegation_data_raw = abi.make(abi.DynamicBytes)
    current_delegation_data = DelegationData()
    header = SignedHeader()
    expires = abi.Uint64()
    # NOTE: Raw scratch var used for performance
    index = ScratchVar(TealType.uint64)

    return Seq(
        # Decode the full delegation chain
        delegation_list.decode(encoded_delegation),

        # Initialize the current signer to the ticket signer
        current_signer.set(target.get()),

        # Iterate the delegation chain
        For(index.store(Int(0)), index.load() < delegation_list.length(), index.store(index.load() + Int(1))).Do(
            # Load the current delegation data
            delegation_list[index.load()].store_into(current_signed_data),

            # Get the signer of the current delegation data
            current_signed_data.signer.store_into(data_signer),

            # Verify the current signer is the signer of the current delegation data
            Assert(current_signer.get() == data_signer.get()),

            # Verify the current delegation data signature
            cast(Expr, verify_signature(current_signer, current_signed_data)),

            # Decode the delegation data and set up for the next iteration
            current_signed_data.operation.store_into(delegation_data_raw),
            current_delegation_data.decode(delegation_data_raw.get()),
            current_delegation_data.delegate.store_into(current_signer),
            current_delegation_data.operation.store_into(operation),

            # Validate the operation was a delegation
            Assert(operation.get() == OperationId.Delegate),

            # Validate the delegation is not expired
            current_delegation_data.expires.store_into(expires),
            Assert(Or(expires.get() == Int(0), expires.get() >= Txn.first_valid_time())),
        ),

        # Check the last signer is aiming at the user proxy
        ticket.signer.store_into(data_signer),
        Assert(current_signer.get() == data_signer.get()),
        cast(Expr, verify_signature(data_signer, ticket)),

        # Validate the data of the ticket starts with the correct header
        ticket.header.store_into(header),
        header.target.use(lambda t: Assert(t.get() == target.get())),
        header.lease.use(lambda lease:
            header.last_valid.use(lambda last_valid:
                Assert(
                    Or(
                        And(lease.get() == Txn.lease(), last_valid.get() >= Txn.last_valid()),
                        last_valid.get() == Int(0),
                    )
                )
            )
        ),
    )


def approve_deposit():
    return Seq(
        Assert(
            Or(
                Txn.on_completion() == OnComplete.NoOp,
                Txn.on_completion() == OnComplete.OptIn,
            )
        ),
        Approve(),
    )


def approve_operation(target, encoded_delegation, ticket):
    return Seq(
        Assert(Txn.on_completion() == OnComplete.NoOp),
        verify_signatures(target, encoded_delegation, ticket),
        Approve(),
    )


def user_proxy():
    """User proxy contract entry point"""

    static_data = UserProxyStaticData()
    encoded_target = Txn.application_args[1]
    encoded_ticket = Txn.application_args[2]
    encoded_delegation = Txn.application_args[3]
    target = abi.make(abi.Address)
    ticket = OperationMetaData()

    return Seq (
        # Validate data and transaction
        Assert(Txn.rekey_to() == Global.zero_address()),
        Assert(Txn.close_remainder_to() == Global.zero_address()),
        Assert(Txn.asset_close_to() == Global.zero_address()),
        Assert(Txn.type_enum() == TxnType.ApplicationCall),
        Assert(Txn.fee() == Int(0)),
        Assert(Txn.note() == Bytes("")),
        Assert(Gtxn[Int(0)].type_enum() == TxnType.Payment),

        # Extract static data and validate it
        static_data.decode(Tmpl.Bytes("TMPL_BN_STATIC_DATA")),
        static_data.server.use(lambda server: Assert(Gtxn[Int(0)].sender() == server.get())),

        # For deposits we only recieves the word "deposit" but for other operations we receive the entire ticket
        If(encoded_ticket == Bytes("deposit")).Then(
            approve_deposit()
        ).Else(Seq(
            target.decode(encoded_target),
            ticket.decode(encoded_ticket),
            approve_operation(target, encoded_delegation, ticket)
        ))
    )
