import unittest
from dao.preprocess import Preprocess
import psycopg2
from common.config import DATABASE_CONFIG
import json

class TestPreprocess(unittest.TestCase):
    
    conn = psycopg2.connect(**DATABASE_CONFIG)

    def test_fetch_all_preprocessed(self):
        cur = self.conn.cursor()
        cur.execute("SELECT preprocess FROM preprocess where preprocess.preprocess is not null")
        rows = cur.fetchall()
        self.assertTrue(len(rows) > 0)

        for row in rows:
            json_res = json.loads(row[0])
            print(json_res['callsite'].split('(')[0])