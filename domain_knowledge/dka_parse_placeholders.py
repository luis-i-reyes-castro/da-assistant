#!/usr/bin/env python3
"""
Parsing functions for placeholder substitution
"""

import os
from collections import OrderedDict
from copy import deepcopy

from sofia_utils.io import ( ensure_dir,
                             list_files_starting_with,
                             load_json_file,
                             write_to_json_file )
from sofia_utils.printing import print_ind

from .dk_argument_parsing import parse_arguments
from .dka_placeholder_database import PlaceHolderDatabase


def parse_dict( data : OrderedDict, phDB : PlaceHolderDatabase) -> OrderedDict :
    
    result = OrderedDict()
    
    for outer_key, inner_data in data.items() :
        outer_key_set = phDB.get_first_placeholder( outer_key, 'set')
        if outer_key_set and ( outer_key_set in phDB.set_map ) :
            for element in phDB.set_map[outer_key_set] :
                new_outer_key         = phDB.apply_ph( outer_key, outer_key_set, element)
                result[new_outer_key] = phDB.apply_funs( inner_data, element)
        else :
            result[outer_key] = deepcopy(inner_data)
    
    return result

def parse_connections( data : OrderedDict, phDB : PlaceHolderDatabase) -> OrderedDict :
    
    result = OrderedDict()
    result['sides']   = list(data['sides'])
    result['bridges'] = parse_dict( data['bridges'], phDB)
    result['edges']   = OrderedDict()

    for side in data['edges'] :
        result['edges'][side] = parse_edges( data['edges'][side], phDB)
    
    return result

def parse_edges( data : list, phDB : PlaceHolderDatabase) -> list[list] :
    
    result = []

    for inner_list in data :
        comp_1 = inner_list[0]
        comp_2 = inner_list[1]
        
        set_ph = phDB.get_first_placeholder( comp_1, 'set')
        if set_ph and ( set_ph in phDB.set_map ) :
            for set_element in phDB.set_map[set_ph] :
                new_comp_1 = phDB.apply_ph( comp_1, set_ph, set_element)
                new_comp_2 = phDB.apply_funs( comp_2, set_element)
                result.append( [ new_comp_1, new_comp_2] )
        
        else :
            set_ph = phDB.get_first_placeholder( comp_2, 'set')
            if set_ph and ( set_ph in phDB.set_map ) :
                for set_element in phDB.set_map[set_ph] :
                    new_comp_1 = comp_1
                    new_comp_2 = phDB.apply_ph( comp_2, set_ph, set_element)
                    result.append( [ new_comp_1, new_comp_2] )
            
            else :
                result.append(inner_list)
    
    return result

def expand_entry( entry : dict[ str, object],
                  phDB  : PlaceHolderDatabase) -> list :
    
    entry_obj   = deepcopy(entry)
    entry_obj   = expand_message_lists( entry_obj, phDB)
    placeholder = phDB.get_first_placeholder( entry_obj, 'set')
    if placeholder and ( placeholder in phDB.set_map ) :
        variants = []
        for element in phDB.set_map[placeholder] :
            replaced = phDB.apply_ph( entry_obj, placeholder, element)
            replaced = phDB.apply_funs( replaced, element)
            variants.extend( expand_entry( replaced, phDB) )
        return variants
    return [ entry_obj ]

def expand_message_lists( entry : dict[ str, object],
                          phDB  : PlaceHolderDatabase) -> dict[ str, object] :
    
    causes_data = entry.get('causes')
    if causes_data :
        
        issues_list = causes_data.get('issues')
        if issues_list :
            causes_data['issues'] = phDB.extend_list( issues_list)
        
        signals_list = causes_data.get('signals')
        if signals_list :
            causes_data['signals'] = phDB.extend_list( signals_list)
    
    disagg_list = entry.get('disaggregate')
    if disagg_list :
        entry['disaggregate'] = phDB.extend_list( disagg_list)
    
    return entry

def parse_messages( data : list,
                    phDB : PlaceHolderDatabase) -> OrderedDict :
    
    result = OrderedDict()
    for entry in data :
        
        expanded_entries = expand_entry( entry, phDB)
        for expanded_entry in expanded_entries :
            
            for message in expanded_entry.get( 'messages', []) :
                
                message_key = message.get('key')
                
                message_dict = OrderedDict()
                message_dict['name'] = message.get('name', '')
                
                message_spanish = message.get('name_spanish')
                if message_spanish :
                    message_dict['name_spanish'] = message_spanish
                
                causes_data = expanded_entry.get('causes')
                if causes_data :
                    message_dict['causes'] = deepcopy(causes_data)
                
                disagg_list = expanded_entry.get('disaggregate')
                if disagg_list :
                    message_dict['disaggregate'] = deepcopy(disagg_list)
                
                combined_notes = expanded_entry.get( 'notes', []) \
                               +        message.get( 'notes', [])
                if combined_notes :
                    message_dict['notes'] = combined_notes
                
                more_info_data = expanded_entry.get('more_info')
                if more_info_data :
                    message_dict['more_info'] = deepcopy(more_info_data)
                
                result[message_key] = message_dict
    
    return result

def parse_signals( data : list,
                   phDB : PlaceHolderDatabase) -> OrderedDict :
    
    result = OrderedDict()
    for entry in data :
    
        expanded_entries = expand_entry( entry, phDB)
        for expanded_entry in expanded_entries :
            
            signals_list = list( expanded_entry.get('signals') or [] )
            path_data    = expanded_entry.get('path')
            notes_data   = expanded_entry.get('notes')
            
            for signal_key in signals_list :
                
                signal_entry         = OrderedDict()
                signal_entry['path'] = path_data
                
                if notes_data :
                    signal_entry['notes'] = notes_data
                
                result[signal_key] = signal_entry
    
    return result

def expand_category_data( category : str,
                          file_data,
                          placeholderDB : PlaceHolderDatabase):
    if category in ('components', 'issues') :
        return parse_dict( file_data, placeholderDB)
    if category == 'connections' :
        return parse_connections( file_data, placeholderDB)
    if category == 'messages' :
        return parse_messages( file_data, placeholderDB)
    if category == 'signals' :
        return parse_signals( file_data, placeholderDB)
    raise ValueError( f'Unknown category: {category}')

def expand_directory( dir_input : str,
                      dir_output : str,
                      options_dict : dict[str, bool] ) -> None :
    
    print_ind(f'EXPANDING DOMAIN KNOWLEDGE FROM: {dir_input}')
    ensure_dir(dir_output)
    print_ind(f'Saving files to: {dir_output}')
    
    selected_categories = [ category 
                            for category, enabled in options_dict.items() if enabled ]
    if not selected_categories :
        print_ind('⚠️ No categories selected for expansion.', 1)
        return
    
    path_placeholders = os.path.join( dir_input, 'placeholders.jsonc')
    placeholderDB = PlaceHolderDatabase(path_placeholders)
    
    for category in selected_categories :
        filepaths = list_files_starting_with( dir_input, category, 'json')
        
        if not filepaths :
            print_ind(f'⚠️ No files found for category {category}', 1)
            continue
        
        print_ind(f'Expanding {category} files ({len(filepaths)} found)...')
        
        for path_input in filepaths :
            filename = os.path.basename(path_input)
            path_output = os.path.join( dir_output, filename)
            print_ind(f'Processing file: {path_input}')
            
            file_data   = load_json_file(path_input)
            parsed_data = expand_category_data( category, file_data, placeholderDB)
            
            write_to_json_file( path_output, parsed_data)
            print_ind( 'File data expanded.', 1)
            
            if placeholderDB.contains_placeholders(parsed_data) :
                print_ind('⚠️ WARNING: Post-processing found leftover placeholders!')

def main( argv : list[str] | None = None) -> None :
    dir_input, dir_output, options_dict = parse_arguments( __file__, argv, True)
    expand_directory( dir_input, dir_output, options_dict)
    return

if __name__ == "__main__" :
    main()
