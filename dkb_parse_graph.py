#!/usr/bin/env python3
"""
DKB Components Graph Parsers
"""

import os
import sys

from sofia_utils.io import ( load_json_file,
                             list_files_starting_with,
                             write_to_json_file )
from sofia_utils.printing import print_ind

from dkb_graph import ComponentsGraph


def list_neighbors( data_components  : dict,
                    data_connections : dict) -> None :
    
    comp_graph = ComponentsGraph(data_connections)
    
    for comp_key, item in data_components.items() :
        item['connected_to'] = comp_graph.get_neighbors(comp_key)
    
    return

def compute_signal_paths( data_signals : dict,
                          data_connections : dict) -> None :
    
    comp_graph = ComponentsGraph(data_connections)
    
    for signal_key, item in data_signals.items() :
        path_data = item.get('path')
        if isinstance( path_data, dict) :
            comp_A = path_data.get('comp_A')
            comp_B = path_data.get('comp_B')
            if comp_A and comp_B :
                bridge = path_data.get('bridge')
                item['path_'] = comp_graph.get_path( comp_A, comp_B, bridge)
    
    return

if __name__ == "__main__" :
    
    if len(sys.argv) < 2 :
        script_name = os.path.basename(sys.argv[0]) \
                      if sys.argv else 'dkb_compute_signal_paths.py'
        print_ind(f'Usage: python {script_name} <input_dir>')
        raise SystemExit(1)
    
    dir_input = sys.argv[1]
    
    print_ind(f'PROCESSING COMPONENT GRAPH IN: {dir_input}')
    
    # Load connections
    print_ind(f'Loading connections...')
    data_filename    = os.path.join( dir_input, 'connections.json')
    data_connections = load_json_file(data_filename)
    
    # Load and process components
    filenames = list_files_starting_with( dir_input, 'components_', 'json')
    for filename_ in filenames :
        print_ind(f'Processing file: {filename_}')
        data_components = load_json_file(filename_)
        list_neighbors( data_components, data_connections)
        write_to_json_file( filename_, data_components)
        print_ind( f'Neighbors expanded', 1)
    
    # Load and process signals
    filenames = list_files_starting_with( dir_input, 'signals_', 'json')
    for filename_ in filenames :
        print_ind(f'Processing file: {filename_}')
        data_signals = load_json_file(filename_)
        compute_signal_paths( data_signals, data_connections)
        write_to_json_file( filename_, data_signals)
        print_ind( f'Signal paths expanded', 1)
