#from src.observability.logging import get_logger
"""
from cmath import log10

import structlog

dev_processors = [
    structlog.contextvars.merge_contextvars,  # 🚀 MUST BE FIRST!
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
    structlog.dev.ConsoleRenderer()   # Pretty colors!
]

prod_processors = [
    structlog.contextvars.merge_contextvars,  # 🚀 MUST BE FIRST!
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
    structlog.processors.JSONRenderer()
]

# Choose based on environment
import os

is_dev = os.getenv("ENV") == "development"
is_dev= False
structlog.configure(processors=dev_processors if is_dev else prod_processors)

from structlog import contextvars

contextvars.bind_contextvars(user_id="zz")
"""

from src.observability.logging import get_logger, configure_logging

configure_logging(
    json_output=False,
)
# Get a logger
log1 = get_logger(__name__)
log1.info("hello world", x="ee", y="ff")
log2 = get_logger(__name__)    
log2.warning("hello animals", x="aa", y="bb")

def test():
    log1.info("test")

test()