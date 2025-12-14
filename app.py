#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from flask import ( Flask,
                    request )
from pathlib import Path
from pydantic import ValidationError

from sofia_utils.printing import print_sep
from wa_agents.basemodels import WhatsAppPayload
from wa_agents.queue_db import QueueDB


# Load enviroment variables
load_dotenv()

# Start Flask
app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True

# Start queue database
QUEUE_DB_NAME = os.getenv( "QUEUE_DB_NAME", "queue.sqlite3")
QUEUE_DB_PATH = Path(__file__).parent / QUEUE_DB_NAME
queue_db      = QueueDB(QUEUE_DB_PATH)

# -----------------------------------------------------------------------------------------
# Diagnostic functions

@app.get("/")
def root() :
    return "root ok", 200

@app.route( "/healthz", methods=["GET"])
def healthz() :
    return "ok", 200

@app.get("/debugz")
def debugz() :
    expected = os.getenv( "WA_VERIFY_TOKEN", default = "")
    masked   = ("*" * (len(expected) - 4) + expected[-4:]) if expected else ""
    return {"verify_token_set": bool(expected), "verify_token_tail": masked}, 200

# -----------------------------------------------------------------------------------------
# Webhook functions

@app.route( "/webhook", methods = ["GET"])
def verify() :
    """
    Webhook verification
    """
    
    token     = request.args.get( "hub.verify_token", default = "")
    challenge = request.args.get( "hub.challenge",    default = "")
    expected  =        os.getenv( "WA_VERIFY_TOKEN",  default = "")
    
    if token and challenge and expected and ( token == expected ) :
        return challenge, 200
    
    return "Verification failed", 403

@app.route( "/webhook", methods = ["POST"])
def webhook() :
    """
    Handle incoming messages
    """
    
    data = request.get_json( silent = True) or {}
    print_sep()
    print( "Incoming:", data)
    
    try :
        payload = WhatsAppPayload.model_validate(data)
    except ValidationError as ve :
        return { "status" : "error", "error" : f"Malformed payload: {ve}" }, 200
    
    enqueue_result = False
    try :
        enqueue_result = queue_db.enqueue(payload)
    except Exception as ex :
        return { "status" : "error", "error" : str(ex) }, 200
    
    return { "status": "ok", "enqueued": enqueue_result }, 200

# -----------------------------------------------------------------------------------------
# Debug run

if __name__ == "__main__" :
    app.run( port = 8080, debug = True)
