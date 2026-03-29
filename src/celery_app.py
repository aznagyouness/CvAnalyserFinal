
from celery import Celery
from celery.schedules import crontab
from src.helpers.config import get_settings

settings = get_settings()   


celery_app = Celery(
    "assai celery",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND_URL,
    include=[
        "src.tasks.test_task",
        "src.tasks.creating_tables",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=[settings.CELERY_TASK_SERIALIZER],

    # Reliability
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,

    # Results
    task_ignore_result=False,
    result_expires=3600,

    # Workers
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    worker_cancel_long_running_tasks_on_connection_loss=True,

    # Broker resilience
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,

    # Routing
    task_routes={
        "src.tasks.creating_tables.fct_table_creation": {"queue": "creating_tables"},

    },

    # Timezone
    timezone="UTC",
)

celery_app.conf.task_default_queue = "default"

