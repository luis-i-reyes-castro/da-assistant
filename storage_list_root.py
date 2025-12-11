#!/usr/bin/env python3

from caseflow_agents.DO_spaces_io import b3_list_directories

if __name__ == "__main__" :
    
    print(f"Root directories:")
    
    results = [ obj["Key"] for obj in b3_list_directories("") ]
    if results :
        for key in results :
            print(f"[>] {key}")
    else :
        print("None")
