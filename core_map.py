""" Entry point for compiling the core contract"""

from feature_gates import FeatureGates
FeatureGates.set_sourcemap_enabled(True)

import sys
import click
from pyteal import Mode, OptimizeOptions
from contracts_unified.core.main import CORE_ROUTER

result = CORE_ROUTER.compile(
    version=9,
    assemble_constants=True,
    optimize=OptimizeOptions(scratch_slots=True),
    with_sourcemaps=True,
    annotate_teal=True,
    pcs_in_sourcemap=True,
    annotate_teal_headers=True,
    annotate_teal_concise=False,
)
print(result.approval_sourcemap.annotated_teal)
