"""Define the bytecode dictionary"""

from pyteal import Tmpl

BYTECODE = {
    "user_proxy": [Tmpl.Bytes("TMPL_BN_UP_BYTECODE_0"), Tmpl.Bytes("TMPL_BN_UP_BYTECODE_1")],
    "withdraw_buffer": [Tmpl.Bytes("TMPL_BN_WB_BYTECODE_0"), Tmpl.Bytes("TMPL_BN_WB_BYTECODE_1")]
}
