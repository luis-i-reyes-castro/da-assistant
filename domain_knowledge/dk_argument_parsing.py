#!/usr/bin/env python3
"""
Shared helpers for parsing command-line arguments in DK checkers.
"""

import sys


DATA_TYPES = ( "components",
               "connections",
               "issues",
               "signals",
               "messages" )

OPTION_ALL   = "--everything"
OPTION_FLAGS = { f"--{data_t}" for data_t in DATA_TYPES }
OPTION_FLAGS.add(OPTION_ALL)


def build_option_dict( option : str) -> dict[str, bool] :
    
    return { data_t : option in ( f"--{data_t}", OPTION_ALL )
             for data_t in DATA_TYPES }


def parse_arguments( script_name : str,
                     argv        : list[str],
                     output_dir  : bool = False
                   ) -> tuple[ str, dict[ str, bool]] | tuple[ str, str, dict[ str, bool]] :
    
    args     = list(argv) if argv is not None else sys.argv[1:]
    min_args = 2 if output_dir else 1
    
    if len(args) < min_args :
        usage_options = "|".join(sorted(OPTION_FLAGS))
        usage_parts   = [ "<dir_input>" ]
        if output_dir :
            usage_parts.append("<dir_output>")
        usage = f"Usage: {script_name} {' '.join(usage_parts)} [{usage_options}]"
        raise SystemExit(usage)
    
    dir_input  = args[0]
    dir_output = args[1] if output_dir else None
    
    option_index = 2 if output_dir else 1
    option       = args[option_index] if len(args) > option_index else OPTION_ALL
    
    if option not in OPTION_FLAGS :
        valid_opts = ", ".join(sorted(OPTION_FLAGS))
        msg        = f"Invalid check option: {option}. Valid options: {valid_opts}"
        raise SystemExit(msg)
    
    options_dict = build_option_dict(option)
    
    if output_dir :
        return dir_input, dir_output, options_dict
    
    return dir_input, options_dict
