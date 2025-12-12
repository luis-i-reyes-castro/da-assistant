#!/bin/bash

bash dk_processing.sh T40
bash dk_processing.sh T50
python3 parse_agent_prompts.py
echo ""
