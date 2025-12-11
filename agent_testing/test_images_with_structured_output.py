#!/usr/bin/env python3
"""
Regression helper for validating structured image outputs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from pydantic import BaseModel
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path :
    sys.path.insert( 0, str(PROJECT_ROOT))

from caseflow_agent import Agent
from caseflow_agent_testing_utils import ( load_image_attachment,
                                           resolve_models_env )
from caseflow_basemodels import( AssistantMsg,
                                 UserContentMsg )


PROMPTS = [ "agent_prompts/debug_images_with_structured_output.md" ]


class ImageResults(BaseModel) :
    
    is_vehicle       : bool = False
    vehicle_medium   : Literal[ "land", "sea", "air", "space"] | None = None
    vehicle_category : Literal[ "civilian", "military"]
    vehicle_tags     : list[str] | None


def run_test( image_path : Path, debug : bool = False) -> None :
    
    models = resolve_models_env()
    print(f"AGENT TEST MODEL(S): {models}")
    
    agent = Agent( "test", models)
    agent.load_prompts(PROMPTS)
    
    origin  = "tests/test_agent_images_structured.py"
    case_id = 42
    text    = "Identify vehicles in this image and respond using the structured schema."
    image_data, image_bytes = load_image_attachment(image_path)
    
    context = [ UserContentMsg( origin  = origin,
                                case_id = case_id,
                                text    = text,
                                media   = image_data ) ]
    
    imgs_cache = { image_data.name : image_bytes }
    
    response = agent.get_response( context    = context,
                                   load_imgs  = True,
                                   imgs_cache = imgs_cache,
                                   output_st  = ImageResults,
                                   max_tokens = 1024,
                                   debug      = debug )
    
    if response and not response.is_empty() :
        assistant_msg = AssistantMsg.from_content( origin  = origin,
                                                   case_id = case_id,
                                                   content = response)
        assistant_msg.print()
    
    return


def main() -> None :
    
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument( "image",
                         type = Path,
                         help = "Image used for the debug structured prompt." )
    parser.add_argument( "--debug",
                         action = "store_true",
                         help   = "Pass through debug=True and dump responses." )
    args = parser.parse_args()
    
    if not args.image.exists() :
        raise SystemExit(f"Image not found: {args.image}")
    
    run_test( image_path = args.image, debug = args.debug)


if __name__ == "__main__" :
    main()
