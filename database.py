import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS honeypot_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                enabled INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                role_id INTEGER,
                exempt_bots INTEGER DEFAULT 0,
                UNIQUE(guild_id, user_id, role_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trigger_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                username TEXT,
                attachment_type TEXT,
                timestamp TEXT,
                message_id INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def set_honeypot_channel(self, guild_id: int, channel_id: int, enabled: bool = True):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO honeypot_channels (guild_id, channel_id, enabled)
            VALUES (?, ?, ?)
        ''', (guild_id, channel_id, 1 if enabled else 0))
        conn.commit()
        conn.close()
    
    def get_honeypot_channel(self, guild_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id, enabled FROM honeypot_channels WHERE guild_id = ?', (guild_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {'channel_id': result[0], 'enabled': bool(result[1])}
        return None
    
    def disable_honeypot(self, guild_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE honeypot_channels SET enabled = 0 WHERE guild_id = ?', (guild_id,))
        conn.commit()
        conn.close()
    
    def add_exemption(self, guild_id: int, user_id: int = None, role_id: int = None, exempt_bots: bool = False):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO exemptions (guild_id, user_id, role_id, exempt_bots)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, user_id, role_id, 1 if exempt_bots else 0))
        conn.commit()
        conn.close()
    
    def remove_exemption(self, guild_id: int, user_id: int = None, role_id: int = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM exemptions WHERE guild_id = ? AND user_id = ? AND role_id = ?
        ''', (guild_id, user_id, role_id))
        conn.commit()
        conn.close()
    
    def get_exemptions(self, guild_id: int) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, role_id, exempt_bots FROM exemptions WHERE guild_id = ?', (guild_id,))
        results = cursor.fetchall()
        conn.close()
        return [{'user_id': r[0], 'role_id': r[1], 'exempt_bots': bool(r[2])} for r in results]
    
    def is_exempt(self, guild_id: int, user_id: int, role_ids: List[int], is_bot: bool) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for role_id in role_ids:
            cursor.execute('SELECT exempt_bots FROM exemptions WHERE guild_id = ? AND role_id = ?', (guild_id, role_id))
            if cursor.fetchone():
                conn.close()
                return True
        
        cursor.execute('SELECT exempt_bots FROM exemptions WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
        result = cursor.fetchone()
        if result and result[0]:
            conn.close()
            return True
        
        if is_bot:
            cursor.execute('SELECT exempt_bots FROM exemptions WHERE guild_id = ? AND exempt_bots = 1', (guild_id,))
            if cursor.fetchone():
                conn.close()
                return True
        
        conn.close()
        return False
    
    def log_trigger(self, guild_id: int, channel_id: int, user_id: int, username: str, attachment_type: str, message_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trigger_logs (guild_id, channel_id, user_id, username, attachment_type, timestamp, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (guild_id, channel_id, user_id, username, attachment_type, datetime.utcnow().isoformat(), message_id))
        conn.commit()
        conn.close()
    
    def get_recent_triggers(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT channel_id, user_id, username, attachment_type, timestamp, message_id
            FROM trigger_logs WHERE guild_id = ?
            ORDER BY timestamp DESC LIMIT ?
        ''', (guild_id, limit))
        results = cursor.fetchall()
        conn.close()
        return [{
            'channel_id': r[0],
            'user_id': r[1],
            'username': r[2],
            'attachment_type': r[3],
            'timestamp': r[4],
            'message_id': r[5]
        } for r in results]