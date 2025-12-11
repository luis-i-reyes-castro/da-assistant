#!/usr/bin/env python3

"""
Domain knowledge analysis utilities.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from dk_basemodels import load_dka_components


def parse_args() -> argparse.Namespace :
    parser = argparse.ArgumentParser(
        description = 'Run domain knowledge analysis tasks.'
    )
    parser.add_argument(
        'task',
        choices = [ 'rank_comp_risk' ],
        help = 'Analysis task to execute.'
    )
    parser.add_argument(
        'input_dir',
        help = 'Directory containing the component JSON files.'
    )
    parser.add_argument(
        'output_file',
        help = 'Filename where the analysis result will be written.'
    )
    return parser.parse_args()


def ensure_input_dir( directory : Path) -> None :
    if not directory.exists() :
        raise FileNotFoundError( f'Input directory not found: {directory}')
    if not directory.is_dir() :
        raise NotADirectoryError( f'Input path is not a directory: {directory}')


def rank_comp_risk( dir_input : Path, output_path : Path) -> None :
    component_groups = load_dka_components(dir_input)
    risk_map         = defaultdict(list)
    
    for components in component_groups.values() :
        for comp_key, comp_data in components.items() :
            risk = comp_data.risk
            try :
                risk_value = float(risk)
            except ( TypeError, ValueError) as error :
                raise ValueError(
                    f'Component {comp_key} has invalid risk value: {risk}'
                ) from error
            risk_map[risk_value].append(comp_key)
    
    ranked_components = { risk : sorted(risk_map[risk])
                          for risk in sorted(risk_map) }
    
    output_path.parent.mkdir( parents = True, exist_ok = True )
    with output_path.open( 'w', encoding = 'utf-8') as handle :
        json.dump( ranked_components, handle, indent = 2, sort_keys = False )
        handle.write('\n')


def main() -> None :
    args         = parse_args()
    input_dir    = Path(args.input_dir).expanduser()
    output_path  = Path(args.output_file).expanduser()
    task_name    = args.task
    task_handlers = {
        'rank_comp_risk' : rank_comp_risk
    }
    
    ensure_input_dir(input_dir)
    
    task_handler = task_handlers.get(task_name)
    if task_handler is None :
        raise ValueError( f'Unsupported task: {task_name}')
    
    task_handler( input_dir, output_path)


if __name__ == '__main__' :
    main()
