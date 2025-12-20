import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Start download
        resp = await client.post("http://127.0.0.1:8000/download", json={
            "url": "https://www.youtube.com/watch?v=I5LFTwnJeyM",
            "max_resolution": 720,
            "edit_65s": False
        })
        result = resp.json()
        video_id = result["video_id"]
        print("Download started, video_id:", video_id)

        # Poll status
        while True:
            status_resp = await client.get(f"http://127.0.0.1:8000/status/{video_id}")
            status = status_resp.json()
            print(status)
            if status["status"] in ("done", "error"):
                break
            await asyncio.sleep(1)

asyncio.run(main())
