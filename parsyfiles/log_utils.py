# default logger that prints on stdout
from logging import getLogger, StreamHandler, INFO

import sys

default_logger = getLogger('parsyfiles')
ch = StreamHandler(sys.stdout)
default_logger.addHandler(ch)
default_logger.setLevel(INFO)
