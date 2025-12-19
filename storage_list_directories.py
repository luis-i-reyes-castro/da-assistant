#!/usr/bin/env python3

from dotenv import load_dotenv
from pathlib import Path
from sys import argv

# Load .env so BUCKET_* vars are available to wa_agents.do_bucket_io
load_dotenv()
from wa_agents.do_bucket_io import b3_list_directories


if __name__ == "__main__" :
    
    fname = Path(__file__).name
    usage = f"Usage: {fname} [ Optional: <prefix> ]\n"
    if not len(argv) in ( 1, 2) :
        raise SystemExit(usage)
    
    results = None
    
    if len(argv) == 1 :
        print(f"Root directories:")
        results = list(b3_list_directories(""))
    
    elif len(argv) == 2 :
        prefix = argv[1]
        print(f"Directories with prefix {prefix}:")
        results = list(b3_list_directories(prefix))
    
    if results :
        for key in results :
            print(f"[>] {key}")
    else :
        print("None")
