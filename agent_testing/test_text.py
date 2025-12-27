#!/usr/bin/env python3
"""
Smoke test for plain text responses via OpenRouter.
"""

from __future__ import annotations

import argparse
from dotenv import load_dotenv

from wa_agents.agent import Agent
from wa_agents.basemodels import( AssistantMsg,
                                  UserContentMsg )


load_dotenv("../.env")
MODELS  = [ "mistralai/pixtral-12b" ]
PROMPTS = [ "debug_text.md" ]


def run_test( debug : bool = False) -> None :
    
    print(f"AGENT TEST MODEL(S): {MODELS}")
    
    agent = Agent( "test", MODELS)
    agent.load_prompts(PROMPTS)
    
    msg_text = "Reply with a short greeting and confirm the debug sandbox."
    context  = [ UserContentMsg(text = msg_text) ]
    
    response = agent.get_response( context    = context,
                                   max_tokens = 256,
                                   debug      = debug )
    
    if response and not response.is_empty() :
        assistant_msg = AssistantMsg.from_content(content = response)
        assistant_msg.print()


def main() -> None :
    
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument( "--debug",
                         action = "store_true",
                         help   = "Pass through debug=True and dump responses." )
    args = parser.parse_args()
    
    run_test( debug = args.debug)


if __name__ == "__main__" :
    main()
