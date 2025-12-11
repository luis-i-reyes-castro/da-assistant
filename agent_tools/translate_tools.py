#!/usr/bin/env python3

import os
import sys

dir_current  = os.path.dirname(os.path.realpath(__file__))
dir_parent   = os.path.dirname(dir_current)
sys.path.append(dir_parent)

from utilities_printing import str_ind

def translate_tools_anthropic( target_api : str,
                               fname_in   : str,
                               fname_out  : str ) -> None :
    """
    Translate tool input schema from Anthropic to Mistral, OpenAI or OpenRouter format.
    
    Args:
        target_api : Target API ('mistral', 'openai' or 'openrouter')
        fname_in   : Input JSON file path (Anthropic format)
        fname_out  : Output JSON file path (target format)
    """
    if target_api not in ( 'mistral', 'openai', 'openrouter') :
        raise ValueError(f"Invalid target_api: {target_api}")
    
    # Load input file as string to preserve formatting
    with open( fname_in, 'r') as f :
        content = f.read()
    
    # Remove the outer array brackets and split into individual tool blocks
    content = content.strip()
    if content.startswith( '[') and content.endswith( ']') :
        content = content[ 1 : -1].strip()
    
    # Split by tool blocks (looking for the pattern that starts each tool)
    # Each tool starts with { and ends with } at the same nesting level
    list_tools = []
    current_tool = ""
    brace_count = 0
    in_tool = False
    i = 0
    
    while i < len( content) :
        char = content[ i]
        
        if char == '{' :
            if not in_tool :
                in_tool = True
                current_tool = char
            else :
                current_tool += char
            brace_count += 1
        elif char == '}' :
            current_tool += char
            brace_count -= 1
            if brace_count == 0 and in_tool :
                list_tools.append(current_tool.strip())
                current_tool = ""
                in_tool = False
        else :
            if in_tool :
                current_tool += char
        
        i += 1
    
    # Process each tool to convert to OpenAI format
    list_output_str = []
    for tool in list_tools :
        if tool.strip() :
            # Extract the name and description from the tool
            # Find the name field
            name_start = tool.find( '"name"')
            if name_start == -1 :
                continue
            
            # Find the name value
            name_value_start = tool.find( ':', name_start) + 1
            name_value_end = tool.find( ',', name_value_start)
            if name_value_end == -1 :
                name_value_end = tool.find( '\n', name_value_start)
            name = tool[ name_value_start : name_value_end].strip().strip( '"')
            
            # Find the description field
            desc_start = tool.find( '"description"')
            if desc_start == -1 :
                continue
            
            # Find the description value
            desc_value_start = tool.find( ':', desc_start) + 1
            desc_value_end = tool.find( ',', desc_value_start)
            if desc_value_end == -1 :
                desc_value_end = tool.find( '\n', desc_value_start)
            description = tool[ desc_value_start : desc_value_end].strip().strip( '"')
            
            # Find the input_schema section
            schema_start = tool.find( '"input_schema"')
            if schema_start == -1 :
                continue
            
            # Extract the entire schema object
            schema_brace_start = tool.find( '{', schema_start)
            schema_brace_count = 0
            schema_end = schema_start
            
            for j in range( schema_brace_start, len( tool)) :
                if tool[ j] == '{' :
                    schema_brace_count += 1
                elif tool[ j] == '}' :
                    schema_brace_count -= 1
                    if schema_brace_count == 0 :
                        schema_end = j + 1
                        break
            
            schema_content = tool[ schema_brace_start : schema_end]
            
            # Create the OpenAI format tool
            if target_api == 'openai' :
                output_str = f'''{{
"type" : "function",
"name" : "{name}",
"description" : "{description}",
"parameters"  :
    {{
''' + str_ind( schema_content[2:-1].rstrip(), 0, 'spaces') + f'''
    }},
"strict" : true
}}'''
            elif target_api in ( "mistral", "openrouter" ) :
                output_str = f'''{{
"type" : "function",
"function" :
    {{
    "name"        : "{name}",
    "description" : "{description}",
    "parameters"  :
        {{
''' + str_ind( schema_content[2:-1].rstrip(), 1, 'spaces') + f'''
        }}
    }}
}}'''
            list_output_str.append(output_str)
    
    # Write the output
    with open( fname_out, 'w') as f :
        f.write('[\n')
        for i, tool in enumerate(list_output_str) :
            f.write(tool)
            if i < len(list_output_str) - 1 :
                f.write(',')
            f.write('\n')
        f.write(']\n')


def main() :
    """Main function to run the script from command line."""
    import sys
    
    if len(sys.argv) != 4 :
        print("Usage: python translate_tools.py <target_API> <input_file.json> <output_file.json>")
        print("Target API: 'mistral' | 'openai' | 'openrouter'")
        print("Example: python openai translate_tools.py agent_tools_anthropic.json agent_tools_openai.json")
        sys.exit(1)
    
    target_api  = sys.argv[1]
    input_file  = sys.argv[2]
    output_file = sys.argv[3]

    if not input_file.endswith(".json") :
        raise ValueError(f"Invalid input file: '{input_file}'")
    if not output_file.endswith(".json") :
        raise ValueError(f"Invalid output file: '{output_file}'")
    if input_file == output_file :
        raise ValueError("Output file cannot be the same as the input file")
    
    try :
        translate_tools_anthropic( target_api, input_file, output_file)
        print( f"Successfully converted {input_file} to {output_file}")
    except FileNotFoundError :
        print( f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    except Exception as e :
        print( f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__" :
    main()
