#!/usr/bin/env python3
"""
Validate DKA Domain Knowledge files
"""

import os
from pydantic import ValidationError
from typing import Any

from dk_argument_parsing import parse_arguments
from dk_basemodels import (DKA_Component,
                           DKA_Connections,
                           DKA_Issue,
                           DKA_MessageGroup,
                           DKA_SignalGroup )

from sofia_utilities.file_io import ( list_files_starting_with,
                                      load_json_file )
from sofia_utilities.printing import ( print_ind,
                                       print_validation_errors )


def validate_components( dir_input : str) -> None :
    
    print_ind('Checking components...')
    filenames = list_files_starting_with( dir_input, 'components_', 'json')
    
    if not filenames :
        print_ind('⚠️ No component files found', 1)
        return
    
    for filename in filenames :
        print_ind(f'Processing file: {filename}')
        data : dict[ str, Any] = load_json_file(filename)
        errors_found           = False
        for comp_key, comp_data in data.items() :
            try :
                DKA_Component.model_validate(comp_data)
            except ValidationError as exc :
                errors_found = True
                print_ind( f'❌ Component {comp_key} failed validation', 1)
                print_validation_errors( exc.errors())
        if not errors_found :
            print_ind('✅ Components file passed validation', 1)
    return

def validate_connections( dir_input : str) -> None :
    
    print_ind('Checking connections...')
    filename = os.path.join( dir_input, 'connections.json')
    
    if not os.path.exists(filename) :
        print_ind(f'⚠️ connections.json not found at {filename}', 1)
        return
    
    data : dict[ str, Any] = load_json_file(filename)
    try :
        DKA_Connections.model_validate(data)
    except ValidationError as exc :
        print_ind('❌ connections.json failed validation', 1)
        print_validation_errors( exc.errors())
    else :
        print_ind('✅ connections.json passed validation', 1)
    return

def validate_issues( dir_input : str) -> None :
    
    print_ind('Checking issues...')
    filenames = list_files_starting_with( dir_input, 'issues_', 'json')
    
    if not filenames :
        print_ind('⚠️ No issue files found', 1)
        return
    
    for filename in filenames :
        print_ind(f'Processing file: {filename}')
        data : dict[ str, Any] = load_json_file(filename)
        errors_found           = False
        for issue_key, issue_data in data.items() :
            try :
                DKA_Issue.model_validate(issue_data)
            except ValidationError as exc :
                errors_found = True
                print_ind( f'❌ Issue {issue_key} failed validation', 1)
                print_validation_errors( exc.errors())
        if not errors_found :
            print_ind('✅ Issues file passed validation', 1)
    return

def validate_messages( dir_input : str) -> None :
    
    print_ind('Checking messages...')
    filenames = list_files_starting_with( dir_input, 'messages_', 'json')
    
    if not filenames :
        print_ind('⚠️ No message files found', 1)
        return
    
    for filename in filenames :
        print_ind(f'Processing file: {filename}')
        data : list[Any] = load_json_file(filename)
        errors_found     = False
        if not isinstance( data, list) :
            print_ind( f'❌ {filename} is not a list of message entries', 1)
            continue
        for index, message_group in enumerate( data, start = 1) :
            try :
                DKA_MessageGroup.model_validate(message_group)
            except ValidationError as exc :
                errors_found = True
                print_ind( f'❌ Message entry #{index} failed validation', 1)
                print_validation_errors( exc.errors())
        if not errors_found :
            print_ind('✅ Messages file passed validation', 1)
    return

def validate_signals( dir_input : str) -> None :
    
    print_ind('Checking signals...')
    filenames = list_files_starting_with( dir_input, 'signals_', 'json')
    
    if not filenames :
        print_ind('⚠️ No signal files found', 1)
        return
    
    for filename in filenames :
        print_ind(f'Processing file: {filename}')
        data : list[Any] = load_json_file(filename)
        errors_found     = False
        if not isinstance( data, list) :
            print_ind( f'❌ {filename} is not a list of signal entries', 1)
            continue
        for index, signal_group in enumerate( data, start = 1) :
            try :
                DKA_SignalGroup.model_validate(signal_group)
            except ValidationError as exc :
                errors_found = True
                print_ind( f'❌ Signal entry #{index} failed validation', 1)
                print_validation_errors( exc.errors())
        if not errors_found :
            print_ind('✅ Signals file passed validation', 1)
    return

def main( argv : list[str] | None = None) -> None :
    
    dir_input, option = parse_arguments( __file__, argv)
    print_ind(f'CHECKING DOMAIN KNOWLEDGE IN: {dir_input}')
    
    if option["components"] :
        validate_components(dir_input)
    if option["connections"] :
        validate_connections(dir_input)
    if option["issues"] :
        validate_issues(dir_input)
    if option["signals"] :
        validate_signals(dir_input)
    if option["messages"] :
        validate_messages(dir_input)

if __name__ == "__main__" :
    main()
