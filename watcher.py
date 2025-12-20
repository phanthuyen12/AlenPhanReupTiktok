import asyncio
from googleapiclient.errors import HttpError
from youtube_client import get_latest_video

async def watch_channel(channel_id: str, rotator, interval=1, log_callback=None, video_callback=None):
    """
    Theo dõi video mới của channel.
    log_callback: function nhận string để log vào GUI hoặc file
    video_callback: function nhận video_url khi có video mới
    """
    baseline_video_id = None

    def log(msg, video_link=None):
        print(msg)  # in ra console để debug
        if log_callback:
            # Cập nhật GUI thread-safe
            log_callback(msg, video_link)

    print(f"🔹 Starting watch_channel for {channel_id}")
    
    # ===== 1️⃣ LẤY VIDEO MỚI NHẤT BAN ĐẦU =====
    while baseline_video_id is None:
        token = rotator.current()
        try:
            print(f"⏳ [{channel_id}] Using token {token[:8]} to get latest video")
            result = await asyncio.to_thread(get_latest_video, channel_id, token)

            if result and "video_id" in result and result["video_id"]:
                baseline_video_id = result["video_id"]
                log(f"▶ [{channel_id}] baseline set = {baseline_video_id}")
                print(f"✅ [{channel_id}] Baseline video ID set")
                break
            else:
                print(f"⚠️ [{channel_id}] No video returned or missing 'video_id', retrying...")
                await asyncio.sleep(2)

        except HttpError as e:
            if e.resp.status in (400, 401, 403):
                old = token
                new = rotator.next()
                log(f"⚠️ [{channel_id}] Token lỗi {old[:8]} → {new[:8]}")
                print(f"⚠️ [{channel_id}] Token lỗi, đổi token")
                await asyncio.sleep(1)

        except Exception as e:
            log(f"❌ [{channel_id}] init error: {e}")
            print(f"❌ [{channel_id}] init error: {e}")
            await asyncio.sleep(5)

    # ===== 2️⃣ THEO DÕI VIDEO MỚI =====
    print(f"🔹 [{channel_id}] Start watching for new videos...")
    while True:
        token = rotator.current()
        try:
            result = await asyncio.to_thread(get_latest_video, channel_id, token)

            if result and "video_id" in result:
                video_id = result["video_id"]

                if video_id != baseline_video_id:
                    baseline_video_id = video_id
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    log(f"🔥 [{channel_id}] NEW VIDEO: {result.get('title', '')} | token {token[:8]}", video_url)
                    print(f"🔥 [{channel_id}] NEW VIDEO detected: {video_url}")
                    # Gọi callback để download và upload
                    if video_callback:
                        await video_callback(video_url)
                else:
                    log(f"⏱ [{channel_id}] no new video, latest = {baseline_video_id}")
                    print(f"⏱ [{channel_id}] Checked: no new video")

            else:
                print(f"⚠️ [{channel_id}] Result empty or missing 'video_id': {result}")

            await asyncio.sleep(interval)

        except HttpError as e:
            if e.resp.status in (400, 401, 403):
                old = token
                new = rotator.next()
                log(f"⚠️ [{channel_id}] Token lỗi {old[:8]} → {new[:8]}")
                print(f"⚠️ [{channel_id}] HttpError token invalid, switch token")
                await asyncio.sleep(1)

        except Exception as e:
            log(f"❌ [{channel_id}] Lỗi khác: {e}")
            print(f"❌ [{channel_id}] Unexpected error: {e}")
            await asyncio.sleep(5)
