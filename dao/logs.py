import psycopg2
from common.config import DATABASE_CONFIG


class PrepLog:
    def __init__(self, item_id, response1, response2, model):
        self.item_id = item_id
        self.response1 = response1
        self.response2 = response2
        self.model = model

    def commit(self):
        _conn = psycopg2.connect(**DATABASE_CONFIG)
        cur = _conn.cursor()
        cur.execute(
            "INSERT INTO preprocess_log (item_id, response1, response2, model) VALUES (%s, %s, %s, %s)",
            (self.item_id, self.response1, self.response2, self.model)
        )
        _conn.commit()
        _conn.close()

class AnalyzeLog:
    def __init__(self, item_id, test_round, dialog_id, req, response, model):
        self.item_id = item_id
        self.test_round = test_round
        self.dialog_id = dialog_id
        self.req = req
        self.response = response
        self.model = model

    def commit(self):
        _conn = psycopg2.connect(**DATABASE_CONFIG)
        cur = _conn.cursor()
        cur.execute(
            "INSERT INTO analysis_log (item_id, test_round, dialog_id, req_abstract, response, model) VALUES (%s, %s, %s, %s, %s, %s)",
            (self.item_id, self.test_round, self.dialog_id, self.req, self.response, self.model)
        )
        _conn.commit()
        _conn.close()