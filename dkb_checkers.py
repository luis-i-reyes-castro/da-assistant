#!/usr/bin/env python3
"""
Validate DKB Domain Knowledge files after placeholder and graph parsing
"""

import os
from collections import OrderedDict
from pydantic import ValidationError

from dk_argument_parsing import parse_arguments
from dk_basemodels import ( DKB_Component,
                            DKB_Connections,
                            DKB_Issue,
                            DKB_SignalEntry,
                            DKB_MessageEntry )
from dkb_graph import ComponentsGraph
from sofia_utilities.file_io import ( list_files_starting_with,
                                      load_json_file )
from sofia_utilities.printing import ( print_ind,
                                       print_validation_errors )


def load_components( dir_input     : str,
                     perform_check : bool,
                     verbose       : bool ) -> OrderedDict[ str, DKB_Component] :
    
    components : OrderedDict[ str, DKB_Component] = OrderedDict()
    filenames = list_files_starting_with( dir_input, "components_", "json")
    
    if verbose :
        header = "Checking components..." if perform_check else "Loading components..."
        print_ind(header)
    
    if not filenames :
        print_ind("⚠️ No component files found", 1)
        return components
    
    for filename in filenames :
        if verbose :
            print_ind(f"Processing file: {filename}")
        data = load_json_file(filename)
        if not isinstance( data, dict) :
            print_ind( f"⚠️ {filename} is not a mapping of components", 1)
            continue
        errors_found = False
        for comp_key, comp_data in data.items() :
            try :
                component = DKB_Component.model_validate(comp_data)
            except ValidationError as exc :
                errors_found = True
                print_ind( f"❌ Component {comp_key} failed validation", 1)
                print_validation_errors(exc.errors())
                continue
            if perform_check and comp_key in components :
                print_ind( f"⚠️ Found repeated component key: {comp_key}", 1)
            components[comp_key] = component
        if verbose and perform_check and not errors_found :
            print_ind( "✅ Components file passed validation", 1)
    
    return components

def load_issues( dir_input     : str,
                 perform_check : bool,
                 verbose       : bool ) -> OrderedDict[ str, DKB_Issue] :
    
    issues : OrderedDict[ str, DKB_Issue] = OrderedDict()
    filenames = list_files_starting_with( dir_input, "issues_", "json")
    
    if verbose :
        header = "Checking issues..." if perform_check else "Loading issues..."
        print_ind(header)
    
    if not filenames :
        print_ind("⚠️ No issue files found", 1)
        return issues
    
    for filename in filenames :
        if verbose :
            print_ind(f"Processing file: {filename}")
        data = load_json_file(filename)
        if not isinstance( data, dict) :
            print_ind( f"⚠️ {filename} is not a mapping of issues", 1)
            continue
        errors_found = False
        for issue_key, issue_dict in data.items() :
            try :
                issue_entry = DKB_Issue.model_validate(issue_dict)
            except ValidationError as exc :
                errors_found = True
                print_ind( f"❌ Issue {issue_key} failed validation", 1)
                print_validation_errors(exc.errors())
                continue
            if perform_check and issue_key in issues :
                print_ind( f"⚠️ Found repeated issue key: {issue_key}", 1)
            issues[issue_key] = issue_entry
        if verbose and perform_check and not errors_found :
            print_ind( "✅ Issues file passed validation", 1)
    
    return issues

def validate_signal_relations( signal_key   : str,
                               signal_entry : DKB_SignalEntry,
                               components   : dict[ str, DKB_Component] ) -> None :
    
    comp_A = signal_entry.path.comp_A
    comp_B = signal_entry.path.comp_B
    path_  = signal_entry.path_
    
    if comp_A not in components :
        msg = f"⚠️ Signal {signal_key}: Path 'comp_A' is not a valid component"
        print_ind( msg, 1)
    if comp_B not in components :
        msg = f"⚠️ Signal {signal_key}: Path 'comp_B' is not a valid component"
        print_ind( msg, 1)
    
    if path_ is None :
        print_ind( f"⚠️ Signal {signal_key} does not have a 'path_' key", 1)
        return
    
    for path_comp in path_ :
        if path_comp not in components :
            msg = f"⚠️ Signal {signal_key}, key 'path_': Invalid component {path_comp}"
            print_ind( msg, 1)
    return

def load_signals( dir_input     : str,
                  components    : dict[ str, DKB_Component],
                  perform_check : bool,
                  verbose       : bool ) -> OrderedDict[ str, DKB_SignalEntry] :
    
    signals : OrderedDict[ str, DKB_SignalEntry] = OrderedDict()
    filenames = list_files_starting_with( dir_input, "signals_", "json")
    
    if verbose :
        header = "Checking signals..." if perform_check else "Loading signals..."
        print_ind(header)
    
    if not filenames :
        print_ind("⚠️ No signal files found", 1)
        return signals
    
    for filename in filenames :
        if verbose :
            print_ind(f"Processing file: {filename}")
        data = load_json_file(filename)
        if not isinstance( data, dict) :
            print_ind( f"⚠️ {filename} is not a mapping of signals", 1)
            continue
        errors_found = False
        for signal_key, signal_dict in data.items() :
            try :
                signal_entry = DKB_SignalEntry.model_validate(signal_dict)
            except ValidationError as exc :
                errors_found = True
                print_ind( f"❌ Signal {signal_key} failed validation", 1)
                print_validation_errors(exc.errors())
                continue
            if perform_check :
                validate_signal_relations( signal_key,
                                           signal_entry,
                                           components)
            if perform_check and signal_key in signals :
                print_ind( f"⚠️ Found repeated signal: {signal_key}", 1)
            signals[signal_key] = signal_entry
        if verbose and perform_check and not errors_found :
            print_ind( "✅ Signals file passed validation", 1)
    
    return signals

def check_connections_relationships( connections : DKB_Connections,
                                     components  : dict[ str, DKB_Component] ) -> bool :
    
    e_found         = False
    components_seen = set()
    pairs_seen      = set()
    
    def check_component( comp : str) -> bool :
        if comp not in components :
            msg = f"⚠️ Invalid component: {comp}"
            print_ind( msg, 1)
            return True
        else :
            components_seen.add(comp)
        return False
    
    def check_pair( comp_pair : tuple[str,str]) -> bool :
        comp_1, comp_2 = comp_pair
        check_component(comp_1)
        check_component(comp_2)
        
        if comp_1 == comp_2 :
            msg = f"⚠️ Self-connection: {comp_1}"
            print_ind( msg, 1)
            return True
        
        pair_forward = ( comp_1, comp_2)
        pair_reverse = ( comp_2, comp_1)
        if pair_forward in pairs_seen or pair_reverse in pairs_seen :
            msg = f"⚠️ Repeated pair: {comp_1} <-> {comp_2}"
            print_ind( msg, 1)
            return True
        else :
            pairs_seen.add(pair_forward)
        
        return False
    
    if len(connections.sides) != 2 :
        print_ind("⚠️ Invalid number of sides", 1)
        e_found = True
    
    for comp in connections.sides :
        e_found = True if check_component(comp) else e_found
    
    for comp, comp_pairs in connections.bridges.items() :
        e_found = True if check_component(comp) else e_found
        for comp_pair in comp_pairs :
            e_found = True if check_pair(tuple(comp_pair)) else e_found
    
    for comp, comp_pairs in connections.edges.items() :
        e_found = True if check_component(comp) else e_found
        for comp_pair in comp_pairs :
            e_found = True if check_pair(tuple(comp_pair)) else e_found
    
    comp_graph = ComponentsGraph(connections.model_dump())
    if not comp_graph.is_tree() :
        print_ind("⚠️ Components graph is not a tree", 1)
        explanation = comp_graph.explain_why_not_tree()
        print_ind( f"Explanation: {explanation}", 2)
    
    missing_components = set(components.keys()) - components_seen
    for comp in sorted(missing_components) :
        print_ind( f"⚠️ Component {comp} is not referenced in connections", 1)
        e_found = True
    
    return e_found

def run_connections_check( dir_input  : str,
                           components : OrderedDict[ str, DKB_Component] ) -> None :
    
    print_ind("Checking connections...")
    filename = os.path.join( dir_input, "connections.json")
    if not os.path.exists(filename) :
        print_ind( f"⚠️ connections.json not found at {filename}", 1)
        return
    
    print_ind(f"Processing file: {filename}")
    data = load_json_file(filename)
    if not isinstance( data, dict) :
        print_ind( f"⚠️ {filename} is not a mapping of connections", 1)
        return
    try :
        connections = DKB_Connections.model_validate(data)
    except ValidationError as exc :
        print_ind( "❌ connections.json failed validation", 1)
        print_validation_errors( exc.errors())
        return
    
    e_found = check_connections_relationships( connections, components)
    
    if not e_found :
        print_ind( "✅ connections.json passed validation", 1)
    
    return

def validate_message_relations( message_key   : str,
                                message_entry : DKB_MessageEntry,
                                components    : dict[ str, DKB_Component],
                                issues        : dict[ str, DKB_Issue],
                                signal_keys   : dict[ str, DKB_SignalEntry] ) -> None :
    
    key_str = str(message_key)
    if not key_str.startswith( ( "error_", "ribbon_", "warning_") ) :
        print_ind( f"⚠️ Message {message_key} has invalid key prefix", 1)
    
    if not key_str.startswith("error_") :
        return
    
    causes = message_entry.causes
    
    has_issues  = bool(causes.issues)  if causes else False
    has_signals = bool(causes.signals) if causes else False
    has_disagg  = bool(message_entry.disaggregate)
    
    if not ( has_issues or has_signals or has_disagg ) :
        print_ind( f"⚠️ Message {message_key}: "
                   f"'causes' and 'disaggregate' are both empty", 1)
    
    if ( has_issues or has_signals ) and has_disagg :
        print_ind( f"⚠️ Message {message_key} has both "
                   f"'causes' and 'disaggregate'", 1)
    
    if causes and causes.issues :
        for issue_key in causes.issues :
            if issue_key not in issues :
                print_ind( f"⚠️ Message {message_key}, in 'causes[issues]': "
                           f"invalid issue: {issue_key}", 1)
    if causes and causes.signals :
        for signal_key in causes.signals :
            if signal_key not in signal_keys :
                print_ind( f"⚠️ Message {message_key}, in 'causes[signals]': "
                           f"invalid signal: {signal_key}", 1)
    
    more_info = message_entry.more_info
    if more_info and more_info.components :
        for comp in more_info.components :
            if comp not in components :
                print_ind( f"⚠️ Message {message_key}, in more_info.components: "
                           f"invalid component: {comp}", 1)
    if more_info and more_info.issues :
        for issue_key in more_info.issues :
            if issue_key not in issues :
                print_ind( f"⚠️ Message {message_key}, in more_info.issues: "
                           f"invalid issue: {issue_key}", 1)
    if more_info and more_info.signals :
        for signal_key in more_info.signals :
            if signal_key not in signal_keys :
                print_ind( f"⚠️ Message {message_key}, in more_info.signals: "
                           f"invalid signal: {signal_key}", 1)
    
    return

def run_messages_check( dir_input  : str,
                        components : OrderedDict[ str, DKB_Component],
                        issues     : OrderedDict[ str, DKB_Issue],
                        signals    : OrderedDict[ str, DKB_SignalEntry] ) -> None :
    
    filenames = list_files_starting_with( dir_input, "messages_", "json")
    if not filenames :
        print_ind("⚠️ No message files found", 1)
        return
    
    print_ind("Checking messages...")
    seen_msg_keys : set[str] = set()
    seen_issues   : set[str] = set()
    seen_signals  : set[str] = set()
    disagg_checks : list[ tuple[ str, list[str]]] = []
    
    for filename in filenames :
        
        print_ind(f"Processing file: {filename}")
        
        data : dict[ str, dict] = load_json_file(filename)
        if not isinstance( data, dict) :
            print_ind( f"⚠️ {filename} is not a mapping of messages", 1)
            continue
        
        errors_found = False
        for msg_key, msg_dict in data.items() :
            try :
                message_entry = DKB_MessageEntry.model_validate(msg_dict)
            except ValidationError as exc :
                errors_found = True
                print_ind( f"❌ Message {msg_key} failed validation", 1)
                print_validation_errors(exc.errors())
                continue
            
            validate_message_relations( msg_key,
                                        message_entry,
                                        components,
                                        issues,
                                        signals)
            
            if msg_key not in seen_msg_keys :
                seen_msg_keys.add(msg_key)
            else :
                print_ind( f"⚠️ Found repeated message key: {msg_key}", 1)
            
            causes = message_entry.causes
            if causes and causes.issues :
                seen_issues.update(causes.issues)
            if causes and causes.signals :
                seen_signals.update(causes.signals)
            
            more_info = message_entry.more_info
            if more_info and more_info.issues :
                seen_issues.update(more_info.issues)
            if more_info and more_info.signals :
                seen_signals.update(more_info.signals)
            
            if message_entry.disaggregate :
                disagg_checks.append( ( msg_key, message_entry.disaggregate) )
        
        if not errors_found :
            print_ind( "✅ Messages file passed validation", 1)
    
    for msg_key, disagg in disagg_checks :
        for disagg_key in disagg :
            if disagg_key not in seen_msg_keys :
                print_ind( f"⚠️ Message {msg_key}, in 'disaggregate': "
                           f"invalid message key: {disagg_key}", 1)
    
    for issue_key in sorted( set(issues.keys()) - seen_issues ) :
        print_ind( f"⚠️ Issue {issue_key} does not appear in any message", 1)
    
    for signal_key in sorted( set(signals.keys()) - seen_signals ) :
        print_ind( f"⚠️ Signal {signal_key} does not appear in any message", 1)
    
    return

def main( argv : list[str] | None = None) -> None :
    
    dir_input, option = parse_arguments( __file__, argv)
    print_ind(f"CHECKING DOMAIN KNOWLEDGE IN: {dir_input}")
    
    need_components = option["components"]  or \
                      option["connections"] or \
                      option["signals"]     or \
                      option["messages"]
    
    need_issues  = option["issues"]  or option["messages"]
    need_signals = option["signals"] or option["messages"]
    
    components = OrderedDict()
    if need_components :
        components = load_components( dir_input,
                                      perform_check = option["components"],
                                      verbose       = option["components"] )
    
    if option["connections"] :
        run_connections_check( dir_input, components )
    
    issues = OrderedDict()
    if need_issues :
        issues = load_issues( dir_input,
                              perform_check = option["issues"],
                              verbose       = option["issues"] )
    
    signals : OrderedDict[ str, DKB_SignalEntry] = OrderedDict()
    if need_signals :
        signals = load_signals( dir_input,
                                components,
                                perform_check = option["signals"],
                                verbose       = option["signals"] )
    
    if option["messages"] :
        run_messages_check( dir_input, components, issues, signals)
    
    return

if __name__ == "__main__" :
    main()
