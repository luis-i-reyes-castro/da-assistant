#!/usr/bin/env python3

import subprocess
import sys
from getpass import getpass

from caseflow_agents.DO_spaces_io import ( b3_clear_prefix,
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
    
    user = "593995341161"
    if len(sys.argv) == 2 :
        user = str(sys.argv[1])
    
    if authenticate() :
        
        print(f"Clearing dir/key/prefix: {user}")
        try :
            b3_clear_prefix(user)
            print(f"Operation successful.")
        except Exception as ex :
            print(f"Operation failed. Exception: {ex}")
        
        print(f"Root dir/key/prefix structure:")
        results = b3_list_directories("")
        if results :
            for key in results :
                print(f"[>] {key}")
        else :
            print("None")
