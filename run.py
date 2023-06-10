import logging
import argparse
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


from dao.case_sampling import CaseSampling
from dao.sampling_res import SamplingRes
from common.config import DB_CONFIG, EVAL_RES_TABLE
from prompts.call_api import do_preprocess, do_analysis


# Create the engine
engine = create_engine(DB_CONFIG)
Session = sessionmaker(bind=engine)

# This function now uses SQLAlchemy to interact with the database


def fetch_all(group, max_id, min_id, offset, max_number):
    batch_size = 100
    session = Session()

    # count the total number of relevant rows
    count_query = session.query(CaseSampling).filter(
        and_(
            CaseSampling.group == group,
            CaseSampling.var_name.notlike('%$%'),
            CaseSampling.id >= min_id,
            CaseSampling.id <= max_id
        )
    )

    real_max_num = count_query.count()
    max_number = min(max_number, real_max_num)

    logging.info(
        f"Total number: {real_max_num}, analyzing {max_number} functions..."
    )

    while offset < max_number:
        rows = count_query.order_by(CaseSampling.id).offset(
            offset).limit(batch_size).all()
        offset += batch_size
        yield rows

    # Remember to close the session when you're done
    session.close()


def fetch_and_update_ctx(group, max_id, min_id, offset, max_number):
    with Session() as session:
        logging.info("Connected to database...")
        for rows in fetch_all(group, max_id, min_id, offset, max_number):
            # Parse the fetched data
            for case in rows:
                if case.raw_ctx is not None and len(case.raw_ctx) > 0:
                    continue
                case.update_raw_ctx()
                if case.raw_ctx is None:
                    logging.error(
                        f"Failed to update raw_ctx for function {case.function}")
                    continue
                session.add(case)
                logging.info(
                    f"Updated raw_ctx for function {case.function} with context {case.raw_ctx[:20]}...")
            session.commit()


"""
def fetch_and_update_preprocess_result(group, max_id, min_id, offset, max_number, model, max_round=3):
    with Session() as session:
        logging.info("Connected to database...")
        for rows in fetch_all(group, max_id, min_id, offset, max_number):
            # Parse the fetched data
            for case in rows:
                if case.raw_ctx is None:
                    logging.error(f"{case.function}: raw context is None")
                    continue

                if case.last_round >= max_round:
                    continue

                case.last_round += 1
                session.add(case)

                logging.info(
                    f"Preprocessing function {case.function} with context  {case.raw_ctx[:20]}...")

                new_result = do_preprocess(case, model)

                # Fetch the preprocessing result for this case from the database
                preprocess_result = session.query(SamplingRes).filter(
                    SamplingRes.id == case.id).first()

                # If there's an existing result and it's non-empty, check for stability
                if preprocess_result and preprocess_result.result and len(preprocess_result.result) > 1:
                    if preprocess_result.result != new_result:
                        preprocess_result.stable = False
                        logging.error(
                            f"Preprocessing result for function {case.function} with variable {case.var_name} changed!!!")
                        logging.error(
                            f"Old result: {preprocess_result.result}")
                        logging.error(f"New result: {new_result}")
                else:  # If there's no existing result, create a new one
                    preprocess_result = SamplingRes(
                        id=case.id, model=model, result=new_result, group=group, initializer=None, stable=True)
                    session.add(preprocess_result)

                preprocess_result.result = new_result
                logging.info(
                    f"Updated preprocess for function {case.function}, variable {case.var_name} with result {new_result[:100]}...")

                session.commit()
"""


def preprocess_and_analyze(group, max_id, min_id, offset, max_number, model):
    with Session() as session:
        logging.info("Connected to database...")
        for rows in fetch_all(group, max_id, min_id, offset, max_number):
            for case in rows:
                # Skip case if raw context is missing or not enough rounds left
                if case.raw_ctx is None or len(case.raw_ctx) < 15 or case.last_round >= 3:
                    continue

                logging.info(
                    f"Preprocessing function {case.function} with context {case.raw_ctx[:20]}...")

                # Preprocessing
                initializer = do_preprocess(case, model)
                sampling_res = session.query(SamplingRes).filter(
                    SamplingRes.id == case.id, SamplingRes.model == model).first()

                if sampling_res and sampling_res.initializer != initializer:
                    sampling_res.stable = False
                    logging.error(
                        f"Preprocessing result for function {case.function} with variable {case.var_name} changed!!!")
                    logging.error(f"Old result: {sampling_res.initializer}")
                    logging.error(f"New result: {initializer}")

                elif not sampling_res:
                    sampling_res = SamplingRes(
                        id=case.id, model=model, initializer=initializer, group=group, stable=True)
                    session.add(sampling_res)

                sampling_res.initializer = initializer
                logging.info(
                    f"Updated preprocess for function {case.function}, variable {case.var_name} with initializer {initializer[:100]}...")

                case.last_round += 1
                session.commit()

                # Skip analysis if preprocessing result is too short
                if len(initializer) < 15:
                    continue

                logging.info(
                    f"Analyzing function {case.function} with preprocess initializer {initializer[:20]}...")

                # Analysis
                result = do_analysis(sampling_res, case.last_round,  model)
                sampling_res.result = result  # Updating the result with analysis output

                logging.info(
                    f"Updated analysis for function {case.function}, variable {case.var_name} with result {result[:100]}...")

                session.commit()


if __name__ == "__main__":
    # test_preprocess_read_file()
    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)-s %(filename)s:%(lineno)s - %(funcName)20s() :: %(message)s')
    INF = 10000000  # a large number, 10M

    parser = argparse.ArgumentParser(
        description='using arguments to control the # of warnings in database to be processed')
    parser.add_argument('--group', type=int, required=True,
                        help='the group of experiment')
    parser.add_argument('--max_id', type=int, default=INF,
                        help='max id of the warning to be processed; default is INF, id is the original identify from static analysis of UBITect')
    parser.add_argument('--min_id', type=int, default=-INF,
                        help='min id of the warning to be processed; default is -INF')
    parser.add_argument('--offset', type=int, default=0,
                        help='offset of the warning to be processed')
    parser.add_argument('--max_number', type=int, default=INF,
                        help='max number of the warning to be processed; default is ifinite')
    parser.add_argument('--model', type=str, default='gpt-4-0314',
                        help='model to be used, default is gpt-4-0314')
    parser.add_argument('--max_round', type=int, default=1,
                        help="control the max running round of each case; increasing to test the stablity of output")
    # parser.add_argument('--temperature', type=float, default=0.7,
    #                     help="control the max running round of each case; increasing to test the stablity of output")
    args = parser.parse_args()

    fetch_and_update_ctx(args.group, args.max_id, args.min_id,
                         args.offset, args.max_number)
    # fetch_and_update_preprocess_result(
    #     args.group, args.max_id, args.min_id, args.offset, args.max_number, args.model)
    # fetch_and_update_analysis_result(
    #     args.group, args.max_id, args.min_id, args.offset, args.max_number, args.model)
    # conn.close()
    preprocess_and_analyze(args.group, args.max_id, args.min_id,
                           args.offset, args.max_number, args.model)
