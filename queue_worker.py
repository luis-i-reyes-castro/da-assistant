#!/usr/bin/env python3
"""
Background worker that drains the incoming WhatsApp queue and runs CaseHandler.
"""

import gc
import logging
import os
import signal
import sys
import time

from dotenv import load_dotenv
from traceback import format_exc
from typing import Any

from caseflow_agents.basemodels import ( MediaContent,
                                         WhatsAppContact,
                                         WhatsAppMsg )
from caseflow_agents.whatsapp_functions import fetch_media
from casehandler import CaseHandler
from queue_db import QueueDB


load_dotenv()
DRAIN_INTERVAL = float( os.getenv( "QUEUE_DRAIN_INTERVAL", 0.2))
POLL_INTERVAL  = float( os.getenv( "QUEUE_POLL_INTERVAL",  1.5))
RESPONSE_DELAY = float( os.getenv( "QUEUE_RESPONSE_DELAY", 1.5))


class QueueWorker :
    
    def __init__( self, queue_db : QueueDB) -> None :
        
        self.queue = queue_db
        self._stop = False
        
        return
    
    def stop( self, *_ : object) -> None :
        
        self._stop = True
        
        return
    
    def run_once( self) -> bool :
        
        item = self.queue.claim_next()
        if not item :
            return False
        
        db_id = item["db_id"]
        try :
            self._process_user_batch(item)
            self.queue.mark_done(db_id)
        
        except Exception as ex :  # noqa: BLE001
            logging.error( "Worker failed for message %s: %s\n%s",
                           item["message_id"], ex, format_exc())
            self.queue.mark_error( db_id, str(ex))
        
        finally :
            gc.collect()
        
        return True
    
    def _process_user_batch( self, item : dict) -> None :
        
        payload : dict[ str, Any] = item["payload"]
        
        contact_data = payload.get( "contact", [])
        if not contact_data :
            raise ValueError("Payload missing contact")
        
        message_data = payload.get( "message", [])
        if not message_data :
            raise ValueError("Payload missing message")
        
        contact = WhatsAppContact.model_validate(contact_data)
        message = WhatsAppMsg.model_validate( message_data, by_alias = True)
        
        user_id   = message.user
        user_name = contact.profile.name if contact and contact.profile else None
        handler   = CaseHandler( user_id, user_name)
        
        respond = self._process_single_msg( handler, message)
        respond = self._drain_user_messages( handler, user_id, respond)
        
        while respond :
            respond = handler.generate_response( max_tokens = None, debug = False)
        
        return
    
    def _process_single_msg( self,
                             handler : CaseHandler,
                             msg     : WhatsAppMsg ) -> bool :
        
        media_content = None
        if msg.media_data :
            media_bytes   = fetch_media(msg.media_data)
            media_content = MediaContent( mime    = msg.media_data.mime_type,
                                          content = media_bytes)
        
        return handler.process_msg_human( msg, media_content)
    
    def _drain_user_messages( self,
                              handler : CaseHandler,
                              user_id : str,
                              respond : bool ) -> bool :
        
        deadline = time.time() + RESPONSE_DELAY
        
        while time.time() < deadline :
            
            next_item = self.queue.claim_next(user_id)
            if not next_item or ( "payload" not in next_item ) :
                time.sleep(DRAIN_INTERVAL)
                continue
            
            payload      : dict[ str, Any] = next_item.get("payload")
            message_data : dict[ str, Any] = payload.get("message")
            
            if not message_data :
                self.queue.mark_done(next_item["db_id"])
                continue
            
            message = WhatsAppMsg.model_validate( message_data, by_alias = True)
            respond = self._process_single_msg( handler, message) or respond
            
            deadline = time.time() + RESPONSE_DELAY
            
            self.queue.mark_done(next_item["db_id"])
        
        return respond
    
    def serve_forever( self) -> None :
        
        logging.info( "Queue worker started, poll interval = %ss", POLL_INTERVAL)
        
        while not self._stop :
            had_work = self.run_once()
            if not had_work :
                time.sleep(POLL_INTERVAL)
        
        logging.info( "Queue worker stopped")
        
        return


def main() -> int :
    
    logging.basicConfig( level  = logging.INFO,
                         format = "%(asctime)s %(levelname)s %(message)s")
    
    queue  = QueueDB()
    worker = QueueWorker( queue)
    
    signal.signal( signal.SIGTERM, worker.stop)
    signal.signal( signal.SIGINT,  worker.stop)
    
    worker.serve_forever()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
