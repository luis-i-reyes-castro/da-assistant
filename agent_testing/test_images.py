#!/usr/bin/env python3
"""
Image ingestion regression using the debug vision prompt + dummy tool.
"""

from __future__ import annotations

import argparse
from dotenv import load_dotenv
from pathlib import Path

from wa_agents.agent import Agent
from wa_agents.basemodels import( AssistantMsg,
                                  load_media,
                                  UserContentMsg )


load_dotenv("../.env")
MODELS  = [ "mistralai/pixtral-12b" ]
PROMPTS = [ "debug_images.md" ]


def run_test( image_path : Path, debug : bool = False) -> None :
    
    print(f"AGENT TEST MODEL(S): {MODELS}")
    
    agent = Agent( "test", MODELS)
    agent.load_prompts(PROMPTS)
    
    origin  = __file__
    case_id = 42
    text    = "Please describe what you see in the image."
    md, mc  = load_media(image_path)
    
    if not ( md and mc ) :
        print(f"Error: Could not read file {image_path}")
        return
    
    context = [ UserContentMsg( origin  = origin,
                                case_id = case_id,
                                text    = text,
                                media   = md) ]
    
    imgs_cache = { md.name : mc.content }
    
    response = agent.get_response( context    = context,
                                   load_imgs  = True,
                                   imgs_cache = imgs_cache,
                                   max_tokens = 256,
                                   debug      = debug )    
    
    if response and not response.is_empty() :
        assistant_msg = AssistantMsg.from_content( origin  = origin,
                                                   case_id = case_id,
                                                   content = response)
        assistant_msg.print()


def main() -> None :
    
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument( "image",
                         type = Path,
                         help = "Image used for the debug prompt." )
    parser.add_argument( "--debug",
                         action = "store_true",
                         help   = "Pass through debug=True and dump responses." )
    args = parser.parse_args()
    
    if not args.image.exists() :
        raise SystemExit(f"Image not found: {args.image}")
    
    run_test( image_path = args.image, debug = args.debug)


if __name__ == "__main__" :
    main()
