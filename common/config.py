LINUX_PATH = "/home/lanran/data/linux-4.14"
DATABASE_CONFIG = {
    "host": "127.0.0.1",
    "database": "ubidb1",
    "user": "ubiuser1",
    "password": "ubitect",
}

DB_CONFIG = 'postgresql://ubiuser1:ubitect@127.0.0.1:5432/ubidb1'

EVAL_SAMPLING_TABLE = 'case_sampling'
EVAL_RES_TABLE = 'sampling_res'

import os

PREPROCESS_ONLY = 'PREPROCESS_ONLY' in os.environ
SELF_VALIDATE = 'SELF_VALIDATE' in os.environ
ENABLE_PP = 'ENABLE_PP' in os.environ
SIMPLE_MODE = 'SIMPLE_MODE' in os.environ

DEBUG_ON = 'DEBUG_MODE' in os.environ
CRTICAL_ON = 'CRITICAL_MODE' in os.environ
