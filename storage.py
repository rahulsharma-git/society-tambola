"""One locked state row: every draw and winner calculation commits atomically.
PostgreSQL for hosting; SQLite is available only for explicit local demos/tests.
"""
import json
import sqlite3
from contextlib import contextmanager
from engine import initial

class Store:
    def __init__(self, url):
        self.url = url
        self.local = url.startswith('sqlite:///')
        if not self.local and not url.startswith(('postgres://', 'postgresql://')):
            raise ValueError('Use a PostgreSQL connection URL.')
        with self.connection() as conn:
            if not self.local:
                conn.execute('CREATE SCHEMA IF NOT EXISTS tambola_private')
                conn.execute('REVOKE ALL ON SCHEMA tambola_private FROM PUBLIC')
            conn.execute('CREATE TABLE IF NOT EXISTS tambola_state (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
            self.execute(conn, 'INSERT INTO tambola_state(id,body) VALUES(1,?) ON CONFLICT(id) DO NOTHING', (json.dumps(initial()),))

    @contextmanager
    def connection(self):
        if self.local:
            conn = sqlite3.connect(self.url[len('sqlite:///'):], timeout=20)
        else:
            import psycopg
            conn = psycopg.connect(self.url, connect_timeout=15, prepare_threshold=None, options='-c statement_timeout=15000 -c lock_timeout=10000 -c search_path=tambola_private')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, conn, sql, args=()):
        return conn.execute(sql if self.local else sql.replace('?', '%s'), args)

    def read(self):
        with self.connection() as conn:
            return json.loads(conn.execute('SELECT body FROM tambola_state WHERE id=1').fetchone()[0])

    def mutate(self, fn):
        with self.connection() as conn:
            if self.local:
                conn.execute('BEGIN IMMEDIATE')
            suffix = '' if self.local else ' FOR UPDATE'
            game = json.loads(conn.execute('SELECT body FROM tambola_state WHERE id=1' + suffix).fetchone()[0])
            result = fn(game)
            self.execute(conn, 'UPDATE tambola_state SET body=? WHERE id=1', (json.dumps(game),))
            return result
