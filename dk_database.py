#!/usr/bin/env python3
"""
Domain Knowledge Database
"""

from functools import wraps
from math import inf
from pathlib import Path
from thefuzz import process
from thefuzz.fuzz import ratio
from typing import ( Any,
                     Callable )

from sofia_utils.io import write_to_json_string
from sofia_utils.printing import ( print_ind,
                                   print_sep )
from wa_agents.basemodels import InteractiveOption

from dk_basemodels import *
from dka_placeholder_database import PlaceHolderDatabase


class DomainKnowledgeDataBase :
    
    MIN_MATCH_SCORE  = 50
    
    MODELS_AVAILABLE = ( "T40", "T50" )
    TOPICS           = ( "components", "messages" )
    
    LIST_COMPONENTS_FIELDS = { "key", "name", "name_spanish" }
    LIST_MESSAGES_FIELDS   = { "key", "name", "name_spanish" }
    
    JD_FIELDS = {
        "messages"   : { "__all__" :
                         { "key", "name", "name_spanish",
                           "disaggregate", "notes", "ignore" } },
        "components" : { "__all__" :
                         { "key", "name", "name_spanish",
                           "errors", "notes" } },
        "issues"     : { "__all__" :
                         { "key", "name",
                           "notes", "solutions", "errors" } },
    }
    
    def __init__(self) -> None :
        
        self.debug = False
        self.model = None
        
        return
    
    def get_model_options(self) -> list[InteractiveOption] :
    
        return [ InteractiveOption( id = model, title = f"DJI Agras {model}")
                 for model in self.MODELS_AVAILABLE ]
    
    def set_model( self, model : str) -> None :
        
        if self.model :
            return True, f"Model already set to '{self.model}'"
        
        if model and ( model in self.MODELS_AVAILABLE ) :
            
            # Record model and setup Domain Knowledge directories
            self.model   = model
            self.dir_dka = model + "_dka"
            self.dir_dkb = model + "_dkb"
            
            # DKA: Load topics
            self.dka_comp = load_dka_components(self.dir_dka)
            self.dka_issu = load_dka_issues(self.dir_dka)
            self.dka_sign = load_dka_signals(self.dir_dka)
            self.dka_msgs = load_dka_messages(self.dir_dka)
            # DKB: Load topics
            self.dkb_comp = load_dkb_components(self.dir_dkb)
            self.dkb_issu = load_dkb_issues(self.dir_dkb)
            self.dkb_sign = load_dkb_signals(self.dir_dkb)
            self.dkb_msgs = load_dkb_messages(self.dir_dkb)
            
            # DKA: Populate 'key' fields
            for cat_key, cat_components_file in self.dka_comp.items() :
                for comp_key in cat_components_file :
                    self.dka_comp[cat_key][comp_key].key = comp_key
            for cat_key, cat_issues_file in self.dka_issu.items() :
                for issue_key in cat_issues_file :
                    self.dka_issu[cat_key][issue_key].key = issue_key
            
            # DKB: Populate 'key' fields
            for comp_key in self.dkb_comp :
                self.dkb_comp[comp_key].key = comp_key
            for issue_key in self.dkb_issu :
                self.dkb_issu[issue_key].key = issue_key
            for signal_key in self.dkb_sign :
                self.dkb_sign[signal_key].key = signal_key
            for msg_key in self.dkb_msgs :
                self.dkb_msgs[msg_key].key = msg_key
            
            # Initalize placeholder database
            ph_path   = Path(self.dir_dka) / "placeholders.jsonc"
            self.phDB = PlaceHolderDatabase(ph_path)
            
            return False, f"Successfully set model to {model}"
        
        return True, f"Tool 'set_model' called with invalid model '{model}'"
    
    def check_model_initialization(func) :
        @wraps(func)
        def wrapper( self, *args, **kwargs) :
            if getattr( self, 'model', None) :
                return func( self, *args, **kwargs)
            else :
                return True, "Drone model has not been set. Use tool 'set_model' to specify the drone model before using this tool."
        return wrapper
    
    def get_match( self,
                   str_input : str,
                   list_str  : list[str] | tuple[str],
                   score_fun : Callable = ratio
                 ) -> str | None :
        
        if list_str :
            list_matches = process.extract( query   = str_input,
                                            choices = list_str,
                                            scorer  = score_fun )
            if list_matches :
                
                if self.debug :
                    print_sep()
                    print( "MATCH INFORMATION" )
                    print( "SCORE FUNCTION: "
                         + getattr( score_fun, '__name__', str(score_fun)) )
                    print( "INPUT STRING:" )
                    print_ind( str_input, 1, "spaces")
                    print( "MATCHES:" )
                    for i, ( match, match_score) in enumerate( list_matches, 1) :
                        print(f"[{i}] String: {match}")
                        print_ind( f"Score:  {match_score}", 1, "spaces")
                    print_sep()
                
                match_score = list_matches[0][1]
                match_str   = list_matches[0][0]
                
                if match_score >= self.MIN_MATCH_SCORE :
                    return match_str
        
        return None
    
    @check_model_initialization
    def list_messages(self) -> str :
        
        result_rows = [ "PLACEHOLDERS" ]
        for set_name, set_elements in self.phDB.set_map.items() :
            result_rows.append( f"<{set_name}> = {", ".join(set_elements)}" )
        
        result_rows.append( "DATABASE IN CSV FORMAT"  )
        result_rows.append( "**KEY**, NAME, NAME_SPANISH" )
        
        for dka_msgs_file in self.dka_msgs.values() :
            for dka_msgs_group in dka_msgs_file :
                for dka_msg_key in dka_msgs_group.messages :
                    row = ", ".join( [ dka_msg_key.key,
                                       dka_msg_key.name,
                                       str(dka_msg_key.name_spanish) ] )
                    result_rows.append(row)
        
        result_str = "; ".join(result_rows)
        result_str = self.phDB.pseudo_XML(result_str)
        
        return result_str
    
    def match_component( self,
                         component : str,
                       ) -> tuple[ bool, str | DKB_Component ] :
        
        matched_comp = self.get_match( component, self.dkb_comp.keys())
        if not matched_comp :
            msg = f"Invalid component: {component}"
            return True, f"In DomainKnowledgeDataBase.match_component: {msg}"
        
        return False, self.dkb_comp.get(matched_comp)
    
    @check_model_initialization
    def get_components( self,
                        components : list[str]
                      ) -> tuple[ bool, Any] :
        
        result : list[ DKB_Component ] = []
        for comp_ in components :
            query_error, matched_comp = self.match_component(comp_)
            if not query_error :
                result.append(matched_comp)
        
        return False, [ comp.model_dump( exclude       = {"risk"},
                                         exclude_unset = True,
                                         exclude_none  = True) for comp in result ]
    
    def match_message( self,
                       message : str,
                     ) -> tuple[ bool, str | DKB_MessageEntry ] :
        
        matched_msg = self.get_match( message, self.dkb_msgs.keys())
        if not matched_msg :
            msg = f"Invalid message: {message}"
            return True, f"In DomainKnowledgeDataBase.match_message: {msg}"
        
        return False, self.dkb_msgs.get(matched_msg)
    
    @check_model_initialization
    def get_joint_diagnosis( self,
                             messages : list[str],
                           ) -> tuple[ bool, Any] :
        
        # Populate list of joint diagnosis message objects
        JD_messages : list[ JD_Message ] = []
        for message_ in messages :
            # Match message
            query_error, matched_msg = self.match_message(message_)
            if not query_error :
                # Instantiate joint diagnosis message object
                msg_obj = JD_Message(**(matched_msg.model_dump()))
                # Flag ribbons and warnings
                if msg_obj.key.startswith( ( 'ribbon_', 'warning_')) :
                    msg_obj.ignore = True
                # Append to joint diagnosis messages
                JD_messages.append(msg_obj)
                # If necessary then disaggregate messages
                if msg_obj.disaggregate :
                    for da_message_ in msg_obj.disaggregate :
                        da_qe, da_mm = self.match_message(da_message_)
                        if not da_qe :
                            da_msg_obj = JD_Message(**(da_mm.model_dump()))
                            JD_messages.append(da_msg_obj)
        
        # Initialize data structures
        component_cards  : dict[ str, int]       = {}
        component_errors : dict[ str, list[str]] = {}
        component_hops   : dict[ str, int]       = {}
        issue_cards      : dict[ str, int]       = {}
        issue_errors     : dict[ str, list[str]] = {}
        
        # Iterate through joint diagnosis message objects
        for message_obj in JD_messages :
            if ( not message_obj.ignore ) and message_obj.causes :
                
                # Initialize and accumulate component cardinalities, errors and hops
                signals = message_obj.causes.signals
                if signals :
                    
                    deduped_components_in_signals : set[str] = set()
                    for signal_ in signals :
                        signal_path_ = self.dkb_sign.get(signal_).path_
                        deduped_components_in_signals.update(signal_path_)
                    
                    for comp in deduped_components_in_signals :
                        component_cards[comp]  = component_cards.get( comp, 0) + 1
                        component_errors[comp] = component_errors.get( comp, []) \
                                               + [ message_obj.key ]
                        for signal_ in signals :
                            signal_path_ = self.dkb_sign.get(signal_).path_
                            if comp in signal_path_ :
                                hops = len(signal_path_) - signal_path_.index(comp) - 1
                                if hops < component_hops.get( comp, +inf) :
                                    component_hops[comp] = hops
                
                # Initialize and accumulate issue cardinalities and errors
                issues = message_obj.causes.issues
                if issues :
                    for issue_ in issues :
                        if not issue_ in issue_cards :
                            issue_cards[issue_] = 0
                        issue_cards[issue_] += 1
                        if not issue_ in issue_errors :
                            issue_errors[issue_] = []
                        issue_errors[issue_].append(message_obj.key)
        
        # Establish component inspection ordering
        comp_io : list[ tuple[ str, int, Decimal] ]
        comp_io = [ ( comp,
                      component_cards.get(comp),
                      self.dkb_comp.get(comp).risk,
                      component_hops.get(comp) )
                    for comp in component_cards.keys() ]
        
        comp_io.sort( key = lambda ct : ( -ct[1],   # Card in descending order
                                          -ct[2],   # Risk in descending order
                                          +ct[3]) ) # Hops in  ascending order
        
        if self.debug :
            _comp_io_ = [ ( ct[0], ct[1], float(ct[2]), ct[3]) for ct in comp_io ]
            print_sep()
            print('COMPONENT INSPECTION ORDERING 4-TUPLES:')
            print(write_to_json_string(_comp_io_))
            print_sep()
        
        # Present component and errors triggered when faulty
        JD_components : list[JD_Component] = []
        for comp, _, _, _ in comp_io :
            comp_obj = JD_Component( **(self.dkb_comp.get(comp).model_dump()) )
            comp_obj.errors = component_errors.get(comp)
            JD_components.append(comp_obj)
        
        # Establish issues inspection ordering
        issues_io : list[ tuple[ str, int] ]
        issues_io = [ ( issue, issue_cards[issue]) for issue in issue_cards.keys() ]
        issues_io.sort( key = lambda i_tup : -i_tup[1]) # Card in descending order
        
        if self.debug :
            print_sep()
            print('ISSUE INSPECTION ORDERING 2-TUPLES:')
            print(write_to_json_string(issues_io))
            print_sep()
        
        # Present issue and errors triggered when present
        JD_issues : list[JD_Issue] = []
        for issue, _ in issues_io :
            issue_obj = JD_Issue( **(self.dkb_issu.get(issue).model_dump()) )
            issue_obj.errors = issue_errors.get(issue)
            JD_issues.append(issue_obj)
        
        # Populate results dict
        result = JointDiagnosis( messages   = JD_messages,
                                 components = JD_components,
                                 issues     = JD_issues )
        
        # The grand finale
        return False, result.model_dump( include       = self.JD_FIELDS,
                                         by_alias      = True,
                                         exclude_unset = True,
                                         exclude_none  = True )
