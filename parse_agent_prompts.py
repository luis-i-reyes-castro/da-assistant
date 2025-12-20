#!/usr/bin/env python3
"""
Generate model-specific agent prompt files by applying placeholders.
"""

import argparse
from pathlib import Path
from typing import Iterable

from sofia_utils.io import ( ensure_dir,
                             load_file_as_string,
                             write_to_file )
from sofia_utils.printing import print_ind

from domain_knowledge.dka_placeholder_database import PlaceHolderDatabase


def parse_arguments() -> argparse.Namespace :
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser( description = 'Expand agent prompts per model.')
    parser.add_argument( '--placeholder-path',
                         default = 'agent_prompts/placeholders.jsonc',
                         help = 'Path to placeholders JSON file.')
    parser.add_argument( '--prompt-dir',
                         default = 'agent_prompts',
                         help = 'Directory containing prompt templates.')
    parser.add_argument( '--templates',
                         nargs = '*',
                         default = ( 'main.md', 'image.md'),
                         help = 'Template filenames to process.')
    parser.add_argument( '--placeholder-set',
                         default = 'MODEL',
                         help = 'Placeholder set to expand (default: MODEL).')
    parser.add_argument( '--output-dir',
                         default = 'agent_prompts',
                         help = 'Optional directory for expanded prompts.')
    return parser.parse_args()


def expand_template_for_value( template_text : str,
                               placeholder_db : PlaceHolderDatabase,
                               placeholder_set : str,
                               set_value : str) -> str :
    """
    Apply set placeholders and functions for a given value.
    """
    expanded_text = placeholder_db.apply_ph( template_text, placeholder_set, set_value)
    expanded_text = placeholder_db.apply_funs( expanded_text, set_value)
    return expanded_text


def resolve_placeholders( template_name : str,
                          set_value     : str,
                          expanded_text : str) -> None :
    """
    Ensure no placeholders remain after expansion.
    """
    if PlaceHolderDatabase.contains_placeholders(expanded_text) :
        msg = ( f'Unresolved placeholders in {template_name} for {set_value}. '
                f'Check template or placeholder data.')
        raise ValueError(msg)
    return


def build_output_path( template_path : Path,
                       output_dir    : Path,
                       set_value     : str) -> Path :
    """
    Build the output path for the expanded prompt file.
    """
    filename = f'{template_path.stem}_{set_value}{template_path.suffix}'
    return output_dir / filename


def iter_set_values( placeholder_db : PlaceHolderDatabase,
                     placeholder_set : str) -> Iterable[str] :
    """
    Yield all values defined for the placeholder set.
    """
    if placeholder_set not in placeholder_db.set_map :
        msg = f"Placeholder set '{placeholder_set}' not found."
        raise ValueError(msg)
    return placeholder_db.set_map[placeholder_set]


def expand_templates( placeholder_db  : PlaceHolderDatabase,
                      template_paths  : list[Path],
                      placeholder_set : str,
                      output_dir      : Path ) -> None :
    """
    Expand each template file for each value in the placeholder set.
    """
    set_values = iter_set_values( placeholder_db, placeholder_set)
    
    for template_path in template_paths :
        print(f"Processing template: {template_path}")
        template_text = load_file_as_string( str(template_path))
        
        for set_value in set_values :
            output_path = build_output_path( template_path, output_dir, set_value)
            print_ind( f"Processing file: {output_path}", 1)
            
            expanded_text = expand_template_for_value( template_text,
                                                       placeholder_db,
                                                       placeholder_set,
                                                       set_value)
            resolve_placeholders( template_path.name, set_value, expanded_text)
            
            ensure_dir(str(output_dir))
            write_to_file( output_path, expanded_text)
            print_ind( "✅ Placeholders expanded and file written", 2)
    
    return


def collect_template_paths( prompt_dir     : Path,
                            template_names : Iterable[str]) -> list[Path] :
    """
    Resolve template filenames to absolute paths and validate existence.
    """
    template_paths : list[Path] = []
    for filename in template_names :
        template_path = prompt_dir / filename
        if not template_path.exists() :
            msg = f"Template file not found: {template_path}"
            raise FileNotFoundError(msg)
        template_paths.append(template_path)
    return template_paths


def main() -> None :
    args = parse_arguments()
    
    placeholder_path = Path(args.placeholder_path).resolve()
    prompt_dir       = Path(args.prompt_dir).resolve()
    output_dir       = Path(args.output_dir).resolve() if args.output_dir else prompt_dir
    
    placeholder_db = PlaceHolderDatabase(str(placeholder_path))
    template_paths = collect_template_paths( prompt_dir, args.templates)
    
    print("")
    print("PROCESSING AGENT PROMPTS")
    print( f"Input dir: {prompt_dir}")
    print( f"Output dir: {output_dir}")
    print( f"Placeholder set: {args.placeholder_set}")
    print( f"Templates: {args.templates}")
    
    expand_templates( placeholder_db,
                      template_paths,
                      args.placeholder_set,
                      output_dir)
    return


if __name__ == '__main__' :
    main()
