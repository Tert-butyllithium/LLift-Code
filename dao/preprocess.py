class Preprocess:
    def __init__(self, id, function, var_name, line_no, file, preprocess, raw_ctx) -> None:
        self.id = id
        self.function = function
        self.var_name = var_name
        self.line_no = line_no
        self.file = file
        self.preprocess = preprocess
        self.raw_ctx = raw_ctx

