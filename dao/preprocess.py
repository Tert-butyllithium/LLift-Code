import logging
from common.config import LINUX_PATH
import os


class Preprocess:
    def __init__(self, id, function, var_name, line_no, file, preprocess, raw_ctx, analysis) -> None:
        self.id = id
        self.function = function
        self.var_name = var_name
        self.line_no = line_no
        self.file = file
        self.preprocess = preprocess
        self.raw_ctx = raw_ctx
        self.analysis = analysis

    def update_raw_ctx(self):
        file_path = os.path.join(LINUX_PATH, self.file)
        function_start = -1

        with open(file_path, 'r', errors='ignore') as f:
            lines = f.readlines()

        for i in range(self.line_no - 1, -1, -1):
            line = lines[i]
            if function_start == -1 and line == "{\n":
                function_start = i + 1

            if function_start != -1:
                break

        if function_start != -1:
            self.raw_ctx = ''.join(lines[function_start:self.line_no])
        else:
            logging.error(f"Function {self.function} not found in the file.")
