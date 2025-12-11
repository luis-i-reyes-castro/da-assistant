"""
Queue Database (SQLite3)
"""

import sqlite3
import threading
from pathlib import Path
from typing import Any

from sofia_utilities.file_io import ( load_json_string,
                                      write_to_json_string )


QUEUE_DB_PATH = Path(__file__).parent / "queue.sqlite3"


class QueueDB :
    """
    Lightweight SQLite-backed queue for incoming WhatsApp messages.
    Guarantees idempotency on message_id via unique constraint.
    """
    
    def __init__( self, db_path : str | Path = QUEUE_DB_PATH) -> None :
        
        self.db_path = str(db_path)
        self._lock   = threading.Lock()
        self._init_db()
        
        return
    
    def _connect(self) -> sqlite3.Connection :
        """
        Connect to database
        """
        conn             = sqlite3.connect( self.db_path, timeout = 30)
        conn.row_factory = sqlite3.Row
        
        return conn
    
    def _init_db(self) -> None :
        """
        Initialize database
        """
        with self._connect() as conn :
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incoming_queue (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id  TEXT NOT NULL UNIQUE,
                    user_id     TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_error  TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incoming_queue_status
                    ON incoming_queue(status);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incoming_queue_user_status
                    ON incoming_queue( user_id, status, created_at);
                """
            )
    
    def enqueue( self, payload : dict[str, Any]) -> bool :
        """
        Insert a payload if not already present.\n
        Args:
            payload: dict with keys 'contacts' and 'messages'
        Returns:
            True if enqueued, False if duplicate.
        """
        if not payload :
            return False
        
        message : dict = payload.get("message")
        msg_id  : str  = message.get("id")
        user_id : str  = message.get("from")
        payload_str    = write_to_json_string( payload, None)
        
        with self._lock, self._connect() as conn :
            try :
                conn.execute(
                    """
                    INSERT INTO incoming_queue ( message_id, user_id, payload)
                    VALUES ( ?, ?, ?)
                    ON CONFLICT(message_id) DO NOTHING;
                    """,
                    ( msg_id, user_id, payload_str),
                )
                return conn.total_changes > 0
            
            except sqlite3.Error :
                return False
    
    def claim_next( self, user_id : str | None = None) -> dict[str, Any] | None :
        """
        Atomically claim the next pending item.\n
        Args:
            user_id: If passed then look for pending items only for that user.
        Returns:
            dict with keys 'db_id', 'message_id', 'user_id', 'payload'.
        """
        with self._lock, self._connect() as conn :
            
            conn.execute( "BEGIN IMMEDIATE;")
            
            where_clause = "status = 'pending'"
            params       = []
            if user_id :
                where_clause = "status = 'pending' AND user_id = ?"
                params       = [ user_id ]
            
            row = conn.execute(
                f"""
                SELECT id, message_id, user_id, payload
                  FROM incoming_queue
                 WHERE {where_clause}
              ORDER BY created_at ASC
                 LIMIT 1;
                """,
                params,
            ).fetchone()
            
            if not row :
                conn.execute( "COMMIT;")
                return None
            
            conn.execute(
                """
                UPDATE incoming_queue
                   SET status     = 'processing',
                       updated_at = CURRENT_TIMESTAMP,
                       last_error = NULL
                 WHERE id = ?;
                """,
                ( row["id"],),
            )
            conn.execute("COMMIT;")
        
        return { "db_id"     : row["id"],
                 "message_id": row["message_id"],
                 "user_id"   : row["user_id"],
                 "payload"   : load_json_string(row["payload"]) }
    
    def mark_done( self, db_id : int) -> None :
        """
        Mark payload as done.\n
        Args:
            db_id: Database ID of the processed payload
        """
        with self._connect() as conn :
            conn.execute(
                """
                UPDATE incoming_queue
                   SET status     = 'done',
                       updated_at = CURRENT_TIMESTAMP
                 WHERE id = ?;
                """,
                ( db_id,),
            )
        return
    
    def mark_error( self, db_id : int, error_msg : str) -> None :
        """
        Mark error during payload processing.\n
        Args:
            db_id     : Database ID of the payload involved
            error_msg : Error message
        """
        with self._connect() as conn :
            conn.execute(
                """
                UPDATE incoming_queue
                   SET status     = 'error',
                       updated_at = CURRENT_TIMESTAMP,
                       last_error = ?
                 WHERE id = ?;
                """,
                ( error_msg[:512], db_id),
            )
        return
