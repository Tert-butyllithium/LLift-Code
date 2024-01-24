LINUX_PATH = "/home/lanran/data/linux-4.14"
DATABASE_CONFIG = {
    "host": "127.0.0.1",
    "database": "ubidb1",
    "user": "ubiuser1",
    "password": "ubitect",
}

DB_CONFIG = 'postgresql://ubiuser1:ubitect@127.0.0.1:5433/ubidb1'

SUP_PROJ = {
    "edk2": "/home/yzhai003/edk2",
    "linux-6.0.2": "/home/yzhai003/linux",
    "nginx": "/Users/lumiali/Downloads/nginx-release-1.18.0"
}

EVAL_SAMPLING_TABLE = 'case_sampling'
EVAL_RES_TABLE = 'sampling_res'

DEFAULT_TEMPERATURE = 1.0

ENABLE_CODEQUERY = True
ENABLE_INTERACTIVE = False
INTERACTIVE_TIMEOUT = 60