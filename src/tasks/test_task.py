from src.celery_app import celery_app
import asyncio

@celery_app.task(
                 bind=True, name="src.tasks.test_task.test_sum",
                 autoretry_for=(Exception,),
                 retry_kwargs={'max_retries': 3, 'countdown': 60}
                ) 
def test_sum(self, x, y):
    result = asyncio.run(_test_sum(self,x, y))
    return result

async def _test_sum(self, x, y):
    await asyncio.sleep(5)  # simulate heavy work
    return x + y

