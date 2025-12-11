#!/usr/bin/env python3
"""
Data structures for placeholder substitution
"""

import dka_regex as phrx
from collections import OrderedDict
from re import ( findall,
                 search,
                 sub )
from typing import Callable
from sofia_utilities.file_io import load_json_file


class BuiltInFunction(dict) :
    def __init__( self, function : Callable[ [str], str]) :
        super().__init__()
        self.function = function
    def __contains__( self, key: object) -> bool :
        return True
    def __getitem__( self, key : str) -> str :
        return self.function(key)
    def __setitem__( self, key : str, value : str) -> None :
        pass

class PlaceHolderDatabase:
    """
    Convenience object for storing all placeholder data
    """
    
    def __init__( self, placeholder_path : str) -> None :
        """
        Initialize placeholder data
        """
        # Load data
        data = load_json_file(placeholder_path)
        
        # Set map: Set name to list of elements
        self.set_map : dict[ str, list[str]] = {}
        # Subset map: Superset name to list of subsets
        self.sub_map : dict[ str, list[str]] = {}
        # Function map: Function name to implementation (dict).
        # Implementation is a dict mapping a set element to function(element).
        self.fun_map : dict[ str, dict[ str, str]] = {}
        
        # Build set map
        sets_data = data.get( 'sets', {})
        for set_name, set_elements in sets_data.items() :
            if not self.is_valid_set(set_elements) :
                print(f"Error: Set '{set_name}' is invalid: {set_elements}")
            self.set_map[set_name] = set_elements
            self.sub_map[set_name] = []
        
        # Process subsets
        subs_data = data.get( 'subsets', {})
        for sub_name, sub_dict in subs_data.items() :
            # Get superset and elements
            superset     = sub_dict.get( 'set', '')
            sub_elements = sub_dict.get( 'elements', [])
            # Check that subset is valid
            if not self.is_valid_sub( superset, sub_elements) :
                print(f"Error: Subset '{sub_name}' is invalid: {sub_elements}")
            # Add to set and subset maps
            self.set_map[sub_name] = sub_elements
            self.sub_map[superset].append(sub_name)
        
        # Build functions declared as dicts
        data = data.get( 'functions', {})
        for fun_name, fun_dict in data.items() :
            if isinstance( fun_dict, dict) :
                if self.is_valid_fun( fun_name, fun_dict) :
                    self.fun_map[fun_name] = fun_dict
                else :
                    print(f"Error: Function '{fun_name}' is invalid: {fun_dict}")
        
        # Build functions declared as strings
        for fun_name, fun_dict in data.items() :
            if isinstance( fun_dict, str) :
                # Function is alias
                if fun_dict in self.fun_map.keys() :
                    self.fun_map[fun_name] = self.fun_map[fun_dict]
                # Function is inverse
                elif fun_dict.startswith("INVERSE:") :
                    orig_fun_name   = fun_dict.replace( "INVERSE:", "").replace( " ", "")
                    orig_fun : dict = self.fun_map.get( orig_fun_name, None)
                    if orig_fun and isinstance( orig_fun, dict) \
                    and ( len(orig_fun) == len( set(orig_fun.values()) ) ) :
                        inv_fun_dict = { val : key for key, val in orig_fun.items() }
                        self.fun_map[fun_name] = inv_fun_dict
                    else :
                        print(f"Error: Function '{fun_name}' is an invalid inverse function, either because function {orig_fun_name} is non-existent or non-invertible.")
                # Function is invalid
                else :
                    print(f"Error: Function '{fun_name}' is invalid: {fun_dict}")
        
        # Check for any invalid function declarations
        for fun_name, fun_dict in data.items() :
            if not ( isinstance( fun_dict, dict) or isinstance( fun_dict, str) ) :
                print(f"Error: Function '{fun_name}' is invalid type '{type(fun_dict)}'")
        
        # Process functions of subsets
        funs_of_subsets = {}
        for fun_name, fun_dict in self.fun_map.items() :
            fun_arg = self.get_arg_set(fun_name)
            if fun_arg in self.sub_map :
                for subset in self.sub_map[fun_arg] :
                    new_fun_name = fun_name.replace( fun_arg, subset)
                    if not new_fun_name in self.fun_map :
                        funs_of_subsets[new_fun_name] = {}
                        for element in self.set_map[subset] :
                            funs_of_subsets[new_fun_name][element]= fun_dict[element]
        if funs_of_subsets :
            self.fun_map.update(funs_of_subsets)
        
        # Add built-in functions
        self.add_built_in_functions()
        
        return
    
    def add_built_in_functions( self) -> None :
        """
        Add built-in functions.
        SAME[SET] is an identity function that returns its argument.
        <FUNCTION>_LOWER[SET] returns FUNCTION[SET] in lower case.
        <FUNCTION>_UPPER[SET] returns FUNCTION[SET] in upper case.
        """
        # Add SAME functions (one for each set)
        for set_name in self.set_map :
            same_func_name = f"SAME[{set_name}]"
            self.fun_map[same_func_name] = BuiltInFunction(lambda x: x)
        # Initialize list of additional functions
        list_add_funs = []
        # Add lower-case function versions
        for fun_name, fun_dict in self.fun_map.items() :
            m_obj = search( phrx.RX_FUN, f"{{{fun_name}}}")
            fun_name, arg_name = m_obj.group(1,2)
            new_func_name = f"{fun_name}_LOWER[{arg_name}]"
            new_func_dict = {}
            for key, val in fun_dict.items() :
                new_func_dict[key] = str(val).lower()
            list_add_funs.append( ( new_func_name, new_func_dict) )
        # Add upper-case function versions
        for fun_name, fun_dict in self.fun_map.items() :
            m_obj = search( phrx.RX_FUN, f"{{{fun_name}}}")
            fun_name, arg_name = m_obj.group(1,2)
            new_func_name = f"{fun_name}_UPPER[{arg_name}]"
            new_func_dict = {}
            for key, val in fun_dict.items() :
                new_func_dict[key] = str(val).upper()
            list_add_funs.append( ( new_func_name, new_func_dict) )
        # Insert additional functions into functions map
        for fun_name, fun_implementation in list_add_funs :
            self.fun_map[fun_name] = fun_implementation
        return
    
    def apply_ph( self,
                  data : str | int | float | list | dict,
                  placeholder : str,
                  argument : str) -> str | list | dict :
        """
        Apply a set or function placeholder to a string
        """
        result = None
        if isinstance( data, str) :
            result = str(data).replace( f'{{{placeholder}}}', argument)
        
        elif isinstance( data, int) or isinstance( data, float) :
            result = data
        
        elif isinstance( data, list) :
            result = []
            for item in data :
                result.append( self.apply_ph( item, placeholder, argument))
        
        elif isinstance( data, dict) :
            result = OrderedDict()
            for key, val in data.items() :
                res_key = self.apply_ph( key, placeholder, argument)
                res_val = self.apply_ph( val, placeholder, argument)
                result[res_key] = res_val
        
        else :
            raise ValueError(f"In apply_ph: Invalid argument type: {type(data)}")
        
        return result
    
    def apply_funs( self,
                    data : str | int | float | list | dict,
                    argument : str) -> str | list | dict :
        
        result = None
        if isinstance( data, str) :
            data_funs = self.get_placeholder_funs(data)
            if data_funs :
                result = data
                for data_fun in data_funs :
                    fun_val = self.fun_map[data_fun][argument]
                    result  = self.apply_ph( result, data_fun, fun_val)
            else:
                result = data
        
        elif isinstance( data, int) or isinstance( data, float) :
            result = data
        
        elif isinstance( data, list) :
            result = []
            for item in data :
                result.append( self.apply_funs( item, argument))
        
        elif isinstance( data, dict) :
            result = OrderedDict()
            for key, val in data.items() :
                res_key = self.apply_funs( key, argument)
                res_val = self.apply_funs( val, argument)
                result[res_key] = res_val
        
        else:
            raise ValueError(f"In eval_apply_funs: Invalid argument type: {type(data)}")
        
        return result
    
    @staticmethod
    def contains_placeholders( data : str | int | float | list | dict) -> bool :
        if isinstance( data, str) :
            match = search( phrx.RX_SET, data)
            if match :
                if match.group(1) not in phrx.IGNORE :
                    return True
            match = search( phrx.RX_FUN, data)
            if match :
                return True
        elif isinstance( data, int) or isinstance( data, float) :
            return False
        elif isinstance( data, list) :
            for item in data :
                if PlaceHolderDatabase.contains_placeholders(item) :
                    return True
        elif isinstance( data, dict) :
            for key, val in data.items() :
                if PlaceHolderDatabase.contains_placeholders(key) \
                or PlaceHolderDatabase.contains_placeholders(val) :
                    return True
        else :
            raise ValueError(f"Invalid argument type: {type(data)}")
        return False
    
    def extend_list( self, data : list) -> list :
        
        result = []
        if isinstance( data, list) :
            for item in data :
                item_set_ph = self.get_first_placeholder( item, 'set')
                if item_set_ph and ( item_set_ph in self.set_map ) :
                    for set_element in self.set_map[item_set_ph] :
                        new_item = self.apply_ph( item, item_set_ph, set_element)
                        result.append(new_item)
                else :
                    result.append(item)
        else:
            raise ValueError(f"In eval_apply_funs: Invalid argument type: {type(data)}")

        return result
    
    def get_arg_set( self, fun_call : str) -> str | None :
        """
        Extract the argument set name from a function call.
        For example, from "ENG[SIDE]" extract "SIDE".
        """
        match = search( phrx.RX_ARG, fun_call)
        return match.group(1) if match else None
    
    def get_first_placeholder( self, 
                               data : str | int | float | list | dict,
                               ph_type : str) -> str | None :
        """
        Get the first placeholder of a given type in the data
        """
        if isinstance( data, str) :
            placeholders = []
            match ph_type:
                case 'set':
                    placeholders = self.get_placeholder_sets(data)
                case 'fun':
                    placeholders = self.get_placeholder_funs(data)
                case _:
                    raise ValueError(f"Invalid placeholder type: {ph_type}")
            if placeholders:
                return placeholders[0]
        
        elif isinstance( data, list) :
            for item in data:
                first_placeholder = self.get_first_placeholder( item, ph_type)
                if first_placeholder :
                    return first_placeholder
        
        elif isinstance( data, dict) :
            for key, val in data.items() :
                first_placeholder = self.get_first_placeholder( key, ph_type)
                if first_placeholder :
                    return first_placeholder
                first_placeholder = self.get_first_placeholder( val, ph_type)
                if first_placeholder :
                    return first_placeholder
        
        return None
    
    def get_placeholder_sets( self, data : str | int | float | list | dict) -> list :
        """
        Get all placeholder sets in data, recursively searching through lists and dicts
        """
        ph_sets = set()
        
        if isinstance( data, str) :
            found_sets = findall( phrx.RX_SET, data)
            for ph in found_sets :
                if ph not in self.set_map :
                    print(f"Error: Set '{ph}' not found in signatures")
                ph_sets.add(ph)
        
        elif isinstance( data, list) :
            for item in data :
                item_sets = self.get_placeholder_sets( item)
                ph_sets.update( item_sets)
        
        elif isinstance( data, dict) :
            for key, val in data.items() :
                key_sets = self.get_placeholder_sets( key)
                val_sets = self.get_placeholder_sets( val)
                ph_sets.update( key_sets)
                ph_sets.update( val_sets)
        
        return list(ph_sets)
    
    def get_placeholder_funs( self, data : str | int | float | list | dict) -> list :
        """
        Get all placeholder functions in data, recursively searching through lists and dicts
        """
        ph_funs = set()
        
        if isinstance( data, str) :
            found_funs = findall( phrx.RX_FUN, data)
            ph_funs_full = [f"{func_name}[{arg_name}]" for func_name, arg_name in found_funs]
            for ph in ph_funs_full :
                if ph not in self.fun_map :
                    print(f"Error: Function '{ph}' not found in signatures")
                ph_funs.add(ph)
        
        elif isinstance( data, list) :
            for item in data :
                item_funs = self.get_placeholder_funs( item)
                ph_funs.update( item_funs)
        
        elif isinstance( data, dict) :
            for key, val in data.items() :
                key_funs = self.get_placeholder_funs( key)
                val_funs = self.get_placeholder_funs( val)
                ph_funs.update( key_funs)
                ph_funs.update( val_funs)
        
        return list(ph_funs)
    
    def is_valid_set( self, set_elements : list) -> bool :
        """
        Check placeholder declaration for correctness: sets
        """
        # Check that set has at least two elements
        if not len(set_elements) >= 2 :
            return False
        # Check that set elements are of the same type
        first_type = type(set_elements[0])
        if not all( isinstance( val, first_type) for val in set_elements ) :
            return False
        # Check that set elements are unique
        if not len(set_elements) == len(set(set_elements)) :
            return False
        # No check failed so set is valid
        return True
    
    def is_valid_sub( self, superset : str, sub_elements : list) -> bool :
        # Check that superset exists
        if not superset in self.set_map :
            return False
        # Check that subset is a valid set
        if not self.is_valid_set(sub_elements) :
            return False
        # Check that subset elements are in superset
        for element in sub_elements :
            if not element in self.set_map[superset] :
                return False
        # No check failed so subset is valid
        return True

    def is_valid_fun( self, fun_name : str, fun_dict : dict) -> bool :
        """
        Check placeholder declaration for correctness: functions
        """
        # Check that function argument is in set_map
        set_name = self.get_arg_set(fun_name)
        if not ( set_name and ( set_name in self.set_map ) ) :
            return False
        # Check that function domain matches argument
        set_elements = self.set_map[set_name]
        if not all( ( element in fun_dict ) for element in set_elements ) :
            return False
        if not all( ( element in set_elements ) for element in fun_dict ) :
            return False
        # No check failed so function is valid
        return True
    
    @staticmethod
    def pseudo_XML( data : str) -> str :
        
        result = sub( fr'{{SAME{phrx.RX_ARG}}}', r'{\1}', data)
        result = sub( phrx.RX_SET, r'<\1>', result)
        
        return result
