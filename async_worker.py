import asyncio

async def async_job(job_id: int, callback):
    for i in range(1, 6):
        callback(f"Job {job_id}: step {i}/5")
        await asyncio.sleep(1)

    callback(f"Job {job_id}: ✅ DONE")

async def run_all_jobs(callback):
    tasks = [
        asyncio.create_task(async_job(i, callback))
        for i in range(5)
    ]
    await asyncio.gather(*tasks)
