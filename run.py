from dao.preprocess import Preprocess
from common.config import DATABASE_CONFIG
import logging
import psycopg2

from prompts.call_api import do_preprocess, do_analysis
import argparse

conn = psycopg2.connect(**DATABASE_CONFIG)

# def test_preprocess_read_file():
#     preprocess = Preprocess(-6, "ov5693_detect", "low", 1710,
#                             "drivers/staging/media/atomisp/i2c/ov5693/ov5693.c", "low", None)
#     preprocess.update_raw_ctx()
#     print(preprocess.raw_ctx)


def fetch_all(cur, max_id, min_id,  offset, max_number):
    batch_size = 100
    cur.execute(
        f"SELECT count(*) FROM preprocess where type != 'unknown' and var_name not like '%$%' and id < {max_id}")
    real_max_num = cur.fetchone()[0]
    max_number = min(max_number, real_max_num)
    logging.info(
        f"Total number: {real_max_num}, analyzing {max_number} functions...")
    while offset < max_number:
        # Fetch data from the PostgreSQL database
        cur.execute(
            f"SELECT * FROM preprocess where type != 'unknown' and var_name not like '%$%' and id < {max_id} and id > {min_id} LIMIT {batch_size} OFFSET {offset}")
        offset += batch_size
        rows = cur.fetchall()
        yield rows


def fetch_and_update_ctx(max_id, min_id, offset, max_number):
    cur = conn.cursor()
    logging.info("Connected to database...")
    for rows in fetch_all(cur, max_id, min_id, offset, max_number):
        # Parse the fetched data
        for row in rows:
            preprocess = Preprocess(
                row[0], row[1], row[3], row[4], row[5], row[6], row[7], row[8])
            if preprocess.raw_ctx is not None and len(preprocess.raw_ctx) > 0:
                continue
            preprocess.update_raw_ctx()
            if preprocess.raw_ctx is None:
                logging.error(
                    f"Failed to update raw_ctx for function {preprocess.function}")
                continue
            cur.execute(
                "UPDATE preprocess SET raw_ctx = %s WHERE id = %s",
                (preprocess.raw_ctx, preprocess.id)
            )
            logging.info(
                f"Updated raw_ctx for function {preprocess.function} with context  {preprocess.raw_ctx[:20]}...")
        conn.commit()
    cur.close()


def fetch_and_update_preprocess_result(max_id, min_id, offset, max_number):
    cur = conn.cursor()
    logging.info("Connected to database...")
    for rows in fetch_all(cur, max_id, min_id, offset, max_number):
        # Parse the fetched data
        for row in rows:
            preprocess = Preprocess(
                row[0], row[1], row[3], row[4], row[5], row[6], row[7], row[8])
            if preprocess.preprocess is not None and len(preprocess.preprocess) > 1:
                continue

            if preprocess.raw_ctx is None:
                logging.error(f"{preprocess.function}: raw context is None")
                continue

            logging.info(
                f"Preprocessing function {preprocess.function} with context  {preprocess.raw_ctx[:20]}...")

            res = None
            for _ in range(3):
                preprocess.preprocess = do_preprocess(preprocess)
                if res is not None and res != preprocess.preprocess:
                    logging.error(
                        f"Preprocessing result for function {preprocess.function} with varaible {preprocess.var_name} changed!!!")
                    logging.error(f"Old result: {res}")
                    logging.error(f"New result: {preprocess.preprocess}")
                    return
                res = preprocess.preprocess
                break

            cur.execute(
                "UPDATE preprocess SET preprocess = %s WHERE id = %s",
                (preprocess.preprocess, preprocess.id)
            )
            logging.info(
                f"Updated preprocess for function {preprocess.function}, varaible {preprocess.var_name} with result {preprocess.preprocess[:100]}...")

            conn.commit()


def fetch_and_update_analysis_result(max_id, min_id, offset, max_number):
    cur = conn.cursor()
    logging.info("Connected to database...")
    for rows in fetch_all(cur, max_id, min_id, offset, max_number):
        # Parse the fetched data
        for row in rows:
            preprocess = Preprocess(
                row[0], row[1], row[3], row[4], row[5], row[6], row[7], row[8])
            if preprocess.preprocess is None or len(preprocess.preprocess) < 15:
                continue

            if preprocess.analysis is not None and len(preprocess.analysis) > 5:
                continue

            logging.info(
                f"Analyzing function {preprocess.function} with preprocess result {preprocess.raw_ctx[:20]}...")

            res = None
            # for _ in range(3):
            # do_preprocess(preprocess)
            # if res is not None and res != preprocess.preprocess:
            #     logging.error(f"Preprocessing result for function {preprocess.function} with varaible {preprocess.var_name} changed!!!")
            #     logging.error(f"Old result: {res}")
            #     logging.error(f"New result: {preprocess.preprocess}")
            #     return
            # res = preprocess.preprocess
            # break
            preprocess.analysis = do_analysis(preprocess)

            if res is None:
                res = "ATTENTION!!!!"

            cur.execute(
                "UPDATE preprocess SET analysis = %s WHERE id = %s",
                (preprocess.analysis, preprocess.id)
            )
            logging.info(
                f"Updated preprocess for id {preprocess.id}, with result {preprocess.analysis[:100]}...")

            conn.commit()


if __name__ == "__main__":
    # test_preprocess_read_file()
    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)-s %(filename)s:%(lineno)s - %(funcName)20s() :: %(message)s')
    INF = 10000000  # a large number, 10M

    parser = argparse.ArgumentParser(
        description='using arguments to control the # of warnings in database to be processed')
    parser.add_argument('--max_id', type=int, default=INF,
                        help='max id of the warning to be processed; default is INF, id is the original identify from static analysis of UBITect')
    parser.add_argument('--min_id', type=int, default=-INF,
                        help='min id of the warning to be processed; default is -INF')
    parser.add_argument('--offset', type=int, default=0,
                        help='offset of the warning to be processed')
    parser.add_argument('--max_number', type=int, default=INF,
                        help='max number of the warning to be processed; default is ifinite')
    args = parser.parse_args()

    fetch_and_update_ctx(args.max_id, args.min_id,
                         args.offset, args.max_number)
    fetch_and_update_preprocess_result(
        args.max_id, args.min_id, args.offset, args.max_number)
    fetch_and_update_analysis_result(
        args.max_id, args.min_id, args.offset, args.max_number)
    conn.close()
