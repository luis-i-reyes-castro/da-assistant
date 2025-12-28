#!/usr/bin/env python3
"""
Regression helper for validating structured image outputs.
"""

from __future__ import annotations

import argparse
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel
from typing import Literal

from wa_agents.agent import Agent
from wa_agents.basemodels import( load_media,
                                  UserContentMsg )


load_dotenv("../.env")
MODELS  = [ "mistralai/pixtral-12b" ]
PROMPTS = [ "debug_images_with_structured_output.md" ]


class ImageResults(BaseModel) :
    
    is_vehicle       : bool = False
    vehicle_medium   : Literal[ "land", "sea", "air", "space"] | None = None
    vehicle_category : Literal[ "civilian", "military"]
    vehicle_tags     : list[str] | None


def run_test( image_path : Path, debug : bool = False) -> None :
    
    print(f"AGENT TEST MODEL(S): {MODELS}")
    
    agent = Agent( "test", MODELS)
    agent.load_prompts(PROMPTS)
    
    msg_text = "Identify vehicles in this image and respond using the structured schema."
    msg_md, msg_mc = load_media(image_path)
    
    if not ( msg_md and msg_mc ) :
        print(f"Error: Could not read file {image_path}")
        return
    
    context    = [ UserContentMsg( text = msg_text, media  = msg_md) ]
    imgs_cache = { msg_md.name : msg_mc.content }
    
    message = agent.get_response( context    = context,
                                  load_imgs  = True,
                                  imgs_cache = imgs_cache,
                                  output_st  = ImageResults,
                                  max_tokens = 1024,
                                  debug      = debug )
    
    if message :
        message.print()
    
    return


def main() -> None :
    
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument( "image",
                         type = Path,
                         help = "Image used for the debug structured prompt." )
    parser.add_argument( "--debug",
                         action = "store_true",
                         help   = "Pass through 'debug = True'" )
    args = parser.parse_args()
    
    if not args.image.exists() :
        raise SystemExit(f"Image not found: {args.image}")
    
    run_test( image_path = args.image, debug = args.debug)


if __name__ == "__main__" :
    main()
