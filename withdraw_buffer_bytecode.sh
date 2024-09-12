#!/bin/bash
set -eo pipefail
BASENAME=wormhole_withdraw_buffer
mkdir -p teal
static_data_mask=$(python3.10 -c "print('FF' * 40, end='')")
python3.10 contracts_unified/$BASENAME/$BASENAME.py teal/$BASENAME.teal
sed "s/TMPL_BN_STATIC_DATA/0x$static_data_mask/" teal/$BASENAME.teal > teal/$BASENAME.replaced.teal
cat teal/$BASENAME.replaced.teal | ($ALGORAND_SANDBOX goal clerk compile -) > teal/$BASENAME.replaced.teal.tok
hexdump -e '8192/1 "%02X" "\n"' teal/$BASENAME.replaced.teal.tok | sed "s/\\(.*\\)$static_data_mask\\([^ ]*\\)[ ]*/\\1\\n\\2/g"
