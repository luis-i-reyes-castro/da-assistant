#!/bin/bash

MODEL="$1"
if [ -z "$MODEL" ]; then
    echo "Usage: $0 <MODEL>"
    exit 1
fi
DIR_INPUT="${MODEL}_dka"
DIR_OUTPUT="${MODEL}_dkb"

# If directory exists then remove all its contents
if [ -d "$DIR_OUTPUT" ]; then
    echo ""
    echo "Removing all JSON files in $DIR_OUTPUT ..."
    rm "$DIR_OUTPUT"/*.json
    echo "Cleanup complete"
fi

# DKA: Run checkers and parse placeholders
echo ""
python3 dka_checkers.py $DIR_INPUT --everything
echo ""
python3 dka_placeholder_parsers.py $DIR_INPUT $DIR_OUTPUT --everything
echo ""
# DKB: Parse components graph and run checkers
python3 dkb_graph_parsers.py $DIR_OUTPUT
echo ""
python3 dkb_checkers.py $DIR_OUTPUT --everything
