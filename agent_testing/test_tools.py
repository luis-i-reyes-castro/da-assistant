#!/usr/bin/env python3
"""
Exercise tool-calling instructions using the debug prompt + DKDB tools.
"""

from __future__ import annotations

import argparse
from dotenv import load_dotenv

from wa_agents.agent import Agent
from wa_agents.basemodels import UserContentMsg


load_dotenv("../.env")
MODELS  = [ "anthropic/claude-3.5-sonnet" ]
PROMPTS = [ "debug_tools.md" ]
TOOLS   = [ "debug_tools.json" ]


def run_test( debug : bool = False) -> None :
    
    print(f"AGENT TEST MODEL(S): {MODELS}")
    
    agent = Agent( "test", MODELS)
    agent.load_prompts(PROMPTS)
    agent.load_tools(TOOLS)
    
    context = [ UserContentMsg(text = "Call both tools") ]
    
    message = agent.get_response( context    = context,
                                  max_tokens = 256,
                                  debug      = debug )
    
    if message :
        message.print()


def main() -> None :
    
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument( "--debug",
                         action = "store_true",
                         help   = "Pass through 'debug = True'" )
    args = parser.parse_args()
    
    run_test( debug = args.debug)


if __name__ == "__main__" :
    main()
