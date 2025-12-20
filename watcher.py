import asyncio
from googleapiclient.errors import HttpError
from youtube_client import get_latest_video

async def watch_channel(channel_id: str, rotator, interval=30):
    baseline_video_id = None

    # ===== 1️⃣ LẤY VIDEO MỚI NHẤT BAN ĐẦU (KHÔNG IN) =====
    while baseline_video_id is None:
        token = rotator.current()
        try:
            result = await asyncio.to_thread(
                get_latest_video,
                channel_id,
                token
            )

            if result and result["video_id"]:
                baseline_video_id = result["video_id"]
                print(
                    f"▶ [{channel_id}] baseline set = {baseline_video_id}"
                )
                break

            await asyncio.sleep(2)

        except HttpError as e:
            if e.resp.status in (400, 401, 403):
                rotator.next()
                await asyncio.sleep(1)

        except Exception as e:
            print(f"❌ [{channel_id}] init error: {e}")
            await asyncio.sleep(5)

    # ===== 2️⃣ THEO DÕI VIDEO MỚI =====
    while True:
        token = rotator.current()
        try:
            result = await asyncio.to_thread(
                get_latest_video,
                channel_id,
                token
            )

            if result:
                video_id = result["video_id"]

                # 🔥 CHỈ IN KHI CÓ VIDEO MỚI
                if video_id != baseline_video_id:
                    baseline_video_id = video_id
                    print(
                        f"🔥 [{channel_id}] NEW VIDEO: "
                        f"{result['title']} | token {token[:8]}"
                    )

            await asyncio.sleep(interval)

        except HttpError as e:
            if e.resp.status in (400, 401, 403):
                old = token
                new = rotator.next()
                print(
                    f"⚠️ [{channel_id}] "
                    f"Token lỗi {old[:8]} → {new[:8]}"
                )
                await asyncio.sleep(1)

        except Exception as e:
            print(f"❌ [{channel_id}] Lỗi khác: {e}")
            await asyncio.sleep(5)
