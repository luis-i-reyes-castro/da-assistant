#!/usr/bin/env python3

import subprocess

from dotenv import load_dotenv
from getpass import getpass
from pathlib import Path
from sys import argv

# Load .env so BUCKET_* vars are available to wa_agents.do_bucket_io
load_dotenv()
from wa_agents.do_bucket_io import ( b3_clear_prefix,
                                     b3_list_directories )


def authenticate() :
    # Get password
    password = getpass("Enter your password: ")
    # Verify password by trying to run a harmless command
    try :
        subprocess.run( [ 'sudo', '-S', 'true'], 
                        input          = password, 
                        text           = True, 
                        capture_output = True,
                        check          = True )
        print("✓ Authentication successful!")
        return True
    # Catch exception: Incorrect pwd
    except subprocess.CalledProcessError :
        print("✗ Authentication failed: Incorrect password")
    # Catch exception: Timeout
    except subprocess.TimeoutExpired :
        print("✗ Authentication timed out")
    # The grand finale
    return False

if __name__ == "__main__" :
    
    fname = Path(__file__).name
    usage = f"Usage: {fname} <prefix> [ Optional: <user> ]\n"
    if not len(argv) in ( 2, 3) :
        raise SystemExit(usage)
    
    prefix = argv[1]
    user   = argv[2] if len(argv) == 3 else "593995341161"
    
    if authenticate() :
        
        full_prefix = f"{prefix}/{user}"
        print(f"Clearing directory: {full_prefix}")
        
        try :
            b3_clear_prefix(full_prefix)
            print(f"Operation successful.")
        except Exception as ex :
            print(f"Operation failed. Exception: {ex}")
        
        print(f"Directories with prefix {prefix}:")
        results = b3_list_directories(prefix)
        if results :
            for key in results :
                print(f"[>] {key}")
        else :
            print("None")
