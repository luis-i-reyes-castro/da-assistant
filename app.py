#!/usr/bin/env python3

import gc
import os
from dotenv import load_dotenv
from flask import Flask
from flask import request

from sofia_utils.printing import print_sep

from queue_db import QueueDB

# Load enviroment variables
load_dotenv()

# Start Flask
app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True

# Start queue database
queue_db = QueueDB()

@app.get("/")
def root() :
    return "root ok", 200

@app.route( "/healthz", methods=["GET"])
def healthz() :
    return "ok", 200

@app.get("/debugz")
def debugz() :
    expected = os.getenv("VERIFY_TOKEN", "")
    masked   = ("*" * (len(expected) - 4) + expected[-4:]) if expected else ""
    return {"verify_token_set": bool(expected), "verify_token_tail": masked}, 200

# --- Webhook verification (GET) ---
@app.route( "/webhook", methods = ["GET"])
def verify() :
    
    token     = request.args.get( "hub.verify_token", default = "")
    challenge = request.args.get( "hub.challenge",    default = "")
    expected  =        os.getenv( "VERIFY_TOKEN",     default = "")
    
    if token and challenge and expected and ( token == expected ) :
        return challenge, 200
    
    return "Verification failed", 403

# --- Handle incoming messages (POST) ---
@app.route( "/webhook", methods = ["POST"])
def webhook() :
    
    data = request.get_json( silent = True) or {}
    print_sep()
    print( "Incoming:", data)
    
    # Fetch payload.
    # Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/reference/messages
    try :
        payload : dict = data["entry"][0]["changes"][0]["value"]
    except ( KeyError, IndexError, TypeError) :
        return "malformed payload", 200
    
    # Only process WhatsApp message events
    if not payload.get("messaging_product") == "whatsapp" :
        return "ignored", 200
    
    contacts = payload.get( "contacts", [])
    if not contacts :
        return "payload missing contacts", 200
    
    messages = payload.get( "messages", [])
    if not messages :
        return "payload missing messages", 200
    
    contact_map = { contact_.get("wa_id") : contact_
                    for contact_ in contacts if contact_.get("wa_id") }
    enqueued = 0
    for message_ in messages :
        msg_from = message_.get("from")
        contact_ = contact_map.get(msg_from)
        queue_payload = { "contact" : contact_,
                          "message" : message_ }
        enqueued += int(queue_db.enqueue(queue_payload))
    
    # Garbage collection
    gc.collect()
    
    return { "status": "ok", "enqueued": enqueued }, 200

if __name__ == "__main__" :
    app.run( port = 8080, debug = True)
