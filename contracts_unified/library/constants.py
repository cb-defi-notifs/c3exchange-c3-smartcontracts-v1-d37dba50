"""
Useful constants to parameterize contracts.
"""

# Wormhole chain ID for algorand
ALGORAND_CHAIN_ID = 8

# Denominator for Ratio type
# TODO: Maybe change this value to something more human readable
# RATIO_ONE = 2**16 - 1
RATIO_ONE = 10**3
RATE_ONE = 10**12

# Maximum fees divisor for orders
MAX_FEES_DIVISOR = 40

# Factor to use to rescale normalized prices from pricecaster
PRICECASTER_RESCALE_FACTOR = 10**9

# Algorand address size
ADDRESS_SIZE = 32
