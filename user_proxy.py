""" Entry point for compiling the account doctor contract"""


import sys
import click
from pyteal import compileTeal, Mode
from contracts_unified.user_proxy.user_proxy import user_proxy


@click.command()
@click.argument("output_approval", type=click.File("w"))
def cli(output_approval):
    output_approval.write(compileTeal(user_proxy(), mode=Mode.Application, version=8))


if __name__ == "__main__":
    cli(sys.argv[1:])
