import psycopg2
from psycopg2.extras import RealDictCursor
import os

class DatabasePostgres:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv('FOCCO_HOST', '192.168.0.10'),
            port=os.getenv('FOCCO_PORT', '5432'),
            database=os.getenv('FOCCO_DB', 'focco'),
            user=os.getenv('FOCCO_USER', 'postgres'),
            password=os.getenv('FOCCO_PASS', 'postgres')
        )
    
    def query(self, sql, params=None):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    
    def query_one(self, sql, params=None):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
