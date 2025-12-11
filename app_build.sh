#!/bin/bash

bash dk_processing.sh T40
bash dk_processing.sh T50
python3 agent_prompt_parsing.py
echo ""
