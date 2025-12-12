#!/usr/bin/env python3

from dotenv import load_dotenv

# Ensure local .env is loaded so SPACES_* vars are available
load_dotenv()

from wa_agents.DO_spaces_io import b3_list_directories


if __name__ == "__main__" :
    
    print(f"Root directories:")
    
    results = list(b3_list_directories(""))
    if results :
        for key in results :
            print(f"[>] {key}")
    else :
        print("None")
