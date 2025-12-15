#!/usr/bin/env python3
"""
Import and run the app's queue worker
"""

import gc
import logging
import os
import signal
import sys

from dotenv import load_dotenv
from pathlib import Path

from wa_agents.queue_db import QueueDB
from wa_agents.queue_worker import QueueWorker

from casehandler import CaseHandler


load_dotenv()
QUEUE_DB_NAME = os.getenv( "QUEUE_DB_NAME", "queue.sqlite3")
QUEUE_DB_PATH = Path(__file__).parent / QUEUE_DB_NAME

def main() -> int :
    
    logging.basicConfig( level  = logging.INFO,
                         format = "%(asctime)s %(levelname)s %(message)s")
    
    queue  = QueueDB(QUEUE_DB_PATH)
    worker = QueueWorker( queue, CaseHandler)
    
    signal.signal( signal.SIGTERM, worker.stop)
    signal.signal( signal.SIGINT,  worker.stop)
    
    worker.serve_forever()
    
    gc.collect()
    
    return 0


if __name__ == "__main__" :
    sys.exit(main())
