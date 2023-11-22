"""
This file implements the router of the Core contract.
"""

from pyteal import (
    BareCallActions,
    CallConfig,
    MethodConfig,
    OnCompleteAction,
    OptimizeOptions,
    Reject,
    Router,
)

from contracts_unified.core.bare_calls import delete, update
from contracts_unified.core.methods import (
    account_move,
    add_order,
    clean_orders,
    create,
    deposit,
    fund_mbr,
    liquidate,
    pool_move,
    portal_transfer,
    settle,
    update_instrument,
    update_parameter,
    withdraw,
    wormhole_deposit,
)

CORE_ROUTER = Router(
    "C3 Core",
    BareCallActions(
        update_application=OnCompleteAction.always(update()),
        delete_application=OnCompleteAction.always(delete()),
    ),
    clear_state=Reject(),
)
CORE_ROUTER.add_method_handler(
    create,
    "create",
    MethodConfig(no_op=CallConfig.CREATE),
    "Create C3 Core contract",
)
CORE_ROUTER.add_method_handler(
    update_instrument,
    "update_instrument",
    MethodConfig(no_op=CallConfig.CALL),
    "Add a new instrument (ASA) to the Core",
)
CORE_ROUTER.add_method_handler(
    update_parameter,
    "update_parameter",
    MethodConfig(no_op=CallConfig.CALL),
    "Update a global parameter",
)
CORE_ROUTER.add_method_handler(
    deposit,
    "deposit",
    MethodConfig(no_op=CallConfig.CALL),
    "Deposit assets to user account",
)
CORE_ROUTER.add_method_handler(
    wormhole_deposit,
    "wormhole_deposit",
    MethodConfig(no_op=CallConfig.CALL),
    "Deposit assets to user account via Wormhole",
)
CORE_ROUTER.add_method_handler(
    pool_move,
    "pool_move",
    MethodConfig(no_op=CallConfig.CALL),
    "Transfer instruments between user and pool",
)
CORE_ROUTER.add_method_handler(
    add_order,
    "add_order",
    MethodConfig(no_op=CallConfig.CALL),
    "Add an order to the order book",
)
CORE_ROUTER.add_method_handler(
    settle,
    "settle",
    MethodConfig(no_op=CallConfig.CALL),
    "Settle two orders"
)
CORE_ROUTER.add_method_handler(
    withdraw,
    "withdraw",
    MethodConfig(no_op=CallConfig.CALL),
    "Withdraw funds from user account",
)
CORE_ROUTER.add_method_handler(
    portal_transfer,
    "portal_transfer",
    MethodConfig(no_op=CallConfig.CALL),
    "Final transaction in a Wormhole deposit group to transfer control from Wormhole Core to CE",
)
CORE_ROUTER.add_method_handler(
    account_move,
    "account_move",
    MethodConfig(no_op=CallConfig.CALL),
    "Moves funds between two accounts",
)
CORE_ROUTER.add_method_handler(
    liquidate,
    "liquidate",
    MethodConfig(no_op=CallConfig.CALL),
    "Liquidate a user's account",
)
CORE_ROUTER.add_method_handler(
    clean_orders,
    "clean_orders",
    MethodConfig(no_op=CallConfig.CALL),
    "Clean expired orders from the order book",
)
CORE_ROUTER.add_method_handler(
    fund_mbr,
    "fund_mbr",
    MethodConfig(no_op=CallConfig.CALL),
    "Fund this contract minimum balance required",
)

CORE_TEAL_APPROVAL, CORE_TEAL_CLEAR, CORE_CONTRACT = CORE_ROUTER.compile_program(
    version=9, assemble_constants=True, optimize=OptimizeOptions(scratch_slots=True)
)
