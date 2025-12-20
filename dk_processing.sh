#!/bin/bash

MODEL="$1"
if [ -z "$MODEL" ]; then
    echo "Usage: $0 <MODEL>"
    exit 1
fi

DIR="domain_knowledge"
DIR_INPUT="${DIR}/${MODEL}_dka"
DIR_OUTPUT="${DIR}/${MODEL}_dkb"

# If directory exists then remove all its contents
if [ -d "$DIR_OUTPUT" ]; then
    echo ""
    echo "Removing all JSON files in $DIR_OUTPUT ..."
    rm "$DIR_OUTPUT"/*.json
    echo "Cleanup complete"
fi

# DKA: Run checkers and parse placeholders
echo ""
python3 -m domain_knowledge.dka_checkers $DIR_INPUT --everything
echo ""
python3 -m domain_knowledge.dka_parse_placeholders $DIR_INPUT $DIR_OUTPUT --everything
echo ""
# DKB: Parse components graph and run checkers
python3 -m domain_knowledge.dkb_parse_graph $DIR_OUTPUT
echo ""
python3 -m domain_knowledge.dkb_checkers $DIR_OUTPUT --everything
