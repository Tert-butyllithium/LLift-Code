from dao.preprocess import Preprocess
from common.config import DATABASE_CONFIG
import logging
import psycopg2

from prompts.call_api import do_preprocess

conn = psycopg2.connect(**DATABASE_CONFIG)

def test_preprocess_read_file():
    preprocess = Preprocess(-6, "ov5693_detect", "low", 1710,
                            "drivers/staging/media/atomisp/i2c/ov5693/ov5693.c", "low", None)
    preprocess.update_raw_ctx()
    print(preprocess.raw_ctx)


def fetch_all(cur):
    batch_size = 10
    offset = 0
    max_number = 20
    while offset < max_number:
        # Fetch data from the PostgreSQL database
        cur.execute(
            f"SELECT * FROM preprocess where id < 200 and type = 'arg_no' LIMIT {batch_size} OFFSET {offset}")
        offset += batch_size

        rows = cur.fetchall()
        yield rows
    


def fetch_and_update_ctx():
    cur = conn.cursor()
    logging.info("Connected to database...")
    for rows in fetch_all(cur):
        # Parse the fetched data
        for row in rows:
            preprocess = Preprocess(
                row[0], row[1], row[3], row[4], row[5], row[6], row[7])
            if preprocess.raw_ctx is not None:
                continue
            preprocess.update_raw_ctx()
            cur.execute(
                "UPDATE preprocess SET raw_ctx = %s WHERE id = %s",
                (preprocess.raw_ctx, preprocess.id)
            )
            logging.info(f"Updated raw_ctx for function {preprocess.function} with context  {preprocess.raw_ctx[:20]}...")
    
    conn.commit()
    conn.close()

def fetch_and_update_preprocess_result():
    cur = conn.cursor()
    logging.info("Connected to database...")
    for rows in fetch_all(cur):
        # Parse the fetched data
        for row in rows:
            preprocess = Preprocess(
                row[0], row[1], row[3], row[4], row[5], row[6], row[7])
            if preprocess.preprocess is not None:
                continue
            
            logging.info(f"Preprocessing function {preprocess.function} with context  {preprocess.raw_ctx[:20]}...")
            
            res = None
            for _ in range(3):
                do_preprocess(preprocess)
                if res is not None and res != preprocess.preprocess:
                    logging.error(f"Preprocessing result for function {preprocess.function} with varaible {preprocess.var_name} changed!!!")
                    logging.error(f"Old result: {res}")
                    logging.error(f"New result: {preprocess.preprocess}")
                    return
                res = preprocess.preprocess
                break
            
            cur.execute(
                "UPDATE preprocess SET preprocess = %s WHERE id = %s",
                (preprocess.preprocess, preprocess.id)
            )
            logging.info(f"Updated preprocess for function {preprocess.function}, varaible {preprocess.var_name} with result {preprocess.preprocess[:100]}...")
    
    conn.commit()
    conn.close()



if __name__ == "__main__":
    # test_preprocess_read_file()
    logging.basicConfig(level=logging.INFO)

    # fetch_and_update_ctx()
    fetch_and_update_preprocess_result()
