import logging
import structlog


log = structlog.get_logger()

user_log= log.bind(app_name="CvanalyserFinal")
user_log.info("Hello, world!", my_name="youness", my_last_name="aznag")

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

"""
structlog.configure(
    processors=[
        # 1️⃣ Add contextvars (request-scoped data) to every log
        structlog.contextvars.merge_contextvars,

        # 2️⃣ Add the log level to the event dict
        structlog.processors.add_log_level,

        # 3️⃣ Add a timestamp
        structlog.processors.TimeStamper(fmt="iso"),

        # 4️⃣ Format the exception stack trace (if any)
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,

        # 5️⃣ FINAL STEP: Render as JSON for production
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.WriteLoggerFactory(),
    cache_logger_on_first_use=True,  # ⚡ Performance boost!
)

log = structlog.get_logger()
log.info("server_started", port=8080, workers=4)
"""

async def handle_request():
    clear_contextvars()  # 🧹 Clean slate for each request

    # Bind once — available to ALL code in this request, even deep in the call stack!
    bind_contextvars(
        request_id="1234567890",
        user_id="123456789012",
        path="/api/v1/welcome/ping_structlog",
    )

    log = structlog.get_logger()
    log.info("request_started")  # Automatically includes request_id, user_id, path!
import asyncio
#asyncio.run(handle_request())

try :
    raise ValueError("Test ValueError")
except ValueError as e:
    log.error("Test ValueError", exc_info=True)