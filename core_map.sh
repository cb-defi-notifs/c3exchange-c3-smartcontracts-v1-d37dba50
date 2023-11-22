#!/bin/bash
set -euo pipefail
mkdir -p maps
python3.10 ./core_map.py > ./maps/core.map
