#!/usr/bin/env python3
"""
Smoke test for plain text responses via OpenRouter.
"""

from __future__ import annotations

import argparse

from wa_agents.agent import Agent
from wa_agents.basemodels import( AssistantMsg,
                                  UserContentMsg )

from agent_testing import resolve_models_env


PROMPTS = [ "../agent_prompts/debug_text.md" ]


def run_test( debug : bool = False) -> None :
    
    models = resolve_models_env()
    print(f"AGENT TEST MODEL(S): {models}")
    
    agent = Agent( "test", models)
    agent.load_prompts(PROMPTS)
    
    origin  = __file__
    case_id = 42
    text    = "Reply with a short greeting and confirm the debug sandbox."
    
    context = [ UserContentMsg( origin = origin, case_id = case_id, text = text) ]
    
    response = agent.get_response( context    = context,
                                   max_tokens = 256,
                                   debug      = debug )
    
    if response and not response.is_empty() :
        assistant_msg = AssistantMsg.from_content( origin  = origin,
                                                   case_id = case_id,
                                                   content = response)
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
