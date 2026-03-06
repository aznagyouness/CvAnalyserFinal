from src.celery_app import celery_app

import asyncio

import time

@celery_app.task(
                 bind=True, name="src.tasks.file_processing.fct",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60}
                ) 
def fct_celery(self, *extra):
    return asyncio.run(_fct(self, *extra))

# don't use celery's async support, it's broken , use asyncio inside a normal celery task instead
# don't use await inside a celery task directly ==> await inside a sync fct is error 

async def _fct(instance, name):
    start = time.time()
    # Your task logic here
    # simultanous tasks example
    await asyncio.gather(
        asyncio.sleep(8) ,asyncio.sleep(5) ,asyncio.sleep(5) 
    )

    end = time.time()
    return f"Hello, {name}!", f"Task completed in {end - start} seconds, the task id is {instance.request.id}  "


