from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

import logging
from common.config import LINUX_PATH, SUP_PROJ
import os


Base = declarative_base()

class CaseSampling(Base):
    __tablename__ = 'case_sampling'
    
    id = Column(Integer, primary_key=True)
    lineno = Column(Integer, nullable=False)
    function = Column(String(255), nullable=False)
    file = Column(String)
    var_name = Column(String)
    last_round = Column(Integer, default=0)
    group = Column('group', Integer)  # As 'group' is a reserved keyword, provide it as a string
    type = Column(String)
    notes = Column(String)
    raw_ctx = Column(Text)
    proj = Column(String)

    def update_raw_ctx(self):
        if self.proj == 'linux':
            proj_path = LINUX_PATH
        elif self.proj in SUP_PROJ:
            proj_path = SUP_PROJ[self.proj]
        else:
            logging.error(f"Project {self.proj} not supported. Check 'SUP_PROJ' in common/config.py")
            return
        file_path = os.path.join(proj_path, self.file)
        function_start = -1

        with open(file_path, 'r', errors='ignore') as f:
            lines = f.readlines()

        for i in range(self.lineno - 1, -1, -1):
            line = lines[i]
            if function_start == -1 and line == "{\n":
                function_start = i + 1

            if function_start != -1:
                break

        if function_start != -1:
            self.raw_ctx = ''.join(lines[function_start:self.lineno])
        else:
            logging.error(f"Function {self.function} not found in the file.")