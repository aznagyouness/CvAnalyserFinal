from src.celery_app import celery_app
import asyncio

@celery_app.task(
                 bind=True, name="src.tasks.file_processing.fct",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60}
                ) 
def test_sum(self, x, y):
    result = asyncio.run(_test_sum(self,x, y))

async def _test_sum(self, x, y):
    await asyncio.sleep(20)  # simulate heavy work
    return x + y

