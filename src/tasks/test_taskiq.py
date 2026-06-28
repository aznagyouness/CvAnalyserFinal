from src.tk_broker import broker
import asyncio

@broker.task(task_name="src.tasks.test_taskiq:my_task")
async def my_task():
    await asyncio.sleep(5)
    return {"status": "done"}


@broker.task(task_name="src.tasks.test_taskiq:my_task2")
async def my_task2(text: str):
    await asyncio.sleep(5)
    return {"status": "done", "text": text}
