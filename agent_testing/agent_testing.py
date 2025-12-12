#!/usr/bin/env python3
"""
Shared helpers for manual agent regression tests.
"""

from __future__ import annotations

import mimetypes
import os
from dotenv import load_dotenv
from pathlib import Path

from sofia_utils.io import load_json_string
from wa_agents.basemodels import MediaData


load_dotenv("..")
DEFAULT_MODELS_SPEC = "openrouter:openrouter/auto"


def resolve_models_env(env_var : str = "AGENT_TEST_MODELS") -> str | list[str]:
    """
    Parse the AGENT_TEST_MODELS environment variable.
    Supported formats:
        * "openrouter:model_a,model_b" -> list[str]
        * "[...]" (JSON array)         -> list[str]
        * "provider:model_id"          -> provider-specific string
        * "<single-model>"             -> provider-specific string
    """
    raw_value = os.environ.get(env_var, DEFAULT_MODELS_SPEC)
    if not raw_value :
        raw_value = DEFAULT_MODELS_SPEC
    raw_value = raw_value.strip()
    
    # JSON array
    if raw_value.startswith("[") :
        try :
            parsed = load_json_string(raw_value)
            if isinstance( parsed, list) :
                models = [ str(m).strip() for m in parsed if str(m).strip() ]
                if models :
                    return models
        except Exception as ex :
            pass
    
    # Prefix-based routing
    if ":" in raw_value :
        prefix, remainder = raw_value.split(":", 1)
        prefix    = prefix.strip().lower()
        remainder = remainder.strip()
        if prefix == "openrouter" :
            models = [ m.strip() for m in remainder.split(",") if m.strip() ]
            if not models :
                raise ValueError("AGENT_TEST_MODELS (openrouter) yielded no models.")
            return models
        else :
            return remainder
    
    # Comma-separated shortcut
    if "," in raw_value :
        models = [ m.strip() for m in raw_value.split(",") if m.strip() ]
        if len(models) == 1 :
            return models[0]
        return models
    
    return raw_value

def load_image_attachment( image_path : Path) -> tuple[ MediaData, bytes] :
    
    image_bytes = image_path.read_bytes()
    attachment  = MediaData( name = image_path.name,
                             mime = mimetypes.guess_type(image_path.name)[0],
                             size = len(image_bytes) )
    
    return attachment, image_bytes
