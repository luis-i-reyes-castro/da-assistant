#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from pathlib import Path

from sofia_utils.io import ensure_dir
from wa_agents.queue_db import QueueDB
from wa_agents.listener import Listener


# Load enviroment variables
load_dotenv()
# Set queue database path
QUEUE_DB_DIR  = os.getenv( "QUEUE_DB_DIR", str(Path(__file__).parent))
QUEUE_DB_NAME = os.getenv( "QUEUE_DB_NAME", "queue.sqlite3")
QUEUE_DB_PATH = Path(QUEUE_DB_DIR).expanduser().resolve() / Path(QUEUE_DB_NAME)
ensure_dir(QUEUE_DB_PATH.parent)


# Instantiate listener app
queue_db = QueueDB(QUEUE_DB_PATH)
app      = Listener( __name__, queue_db)


# Debug run
if __name__ == "__main__" :
    app.run( port = 8080, debug = True)
