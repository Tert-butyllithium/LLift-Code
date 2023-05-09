import psycopg2
from common.config import DATABASE_CONFIG


class PrepLog:
    def __init__(self, item_id, response1, response2):
        self.item_id = item_id
        self.response1 = response1
        self.response2 = response2

    def commit(self):
        _conn = psycopg2.connect(**DATABASE_CONFIG)
        cur = _conn.cursor()
        cur.execute(
            "INSERT INTO preprocess_log (item_id, response1, response2) VALUES (%s, %s, %s)",
            (self.item_id, self.response1, self.response2)
        )
        _conn.commit()
        _conn.close()
