""" Entry point for compiling the core contract"""


import sys
import click

from contracts_unified.core.main import CORE_TEAL_APPROVAL, CORE_TEAL_CLEAR, CORE_CONTRACT
import json


@click.command()
@click.argument("output_approval", type=click.File("w"))
@click.argument("output_clear", type=click.File("w"))
@click.argument("test_fixed_delta", type=str, required=False)
@click.argument("output_abi", type=click.File("w"), required=False)
def cli(output_approval, output_clear, test_fixed_delta, output_abi):
    """Write the compiled contracts"""
    output_approval.write(CORE_TEAL_APPROVAL)
    output_clear.write(CORE_TEAL_CLEAR)
    if (output_abi):
        output_abi.write(json.dumps(CORE_CONTRACT.dictify(), indent=4))

if __name__ == "__main__":
    cli(sys.argv[1:])
