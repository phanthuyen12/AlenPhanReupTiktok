"""
Reup TikTok - NO UI Version (Async)
Full code ~300 lines, giữ nguyên layout gốc, tối ưu tốc độ download API
"""
import asyncio
import os
import re
from datetime import datetime
from loader import TxtLoader
from token_rotator import TokenRotator
from watcher import watch_channel
from utils.tiktok_action import ProfileController
import httpx
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# ---------------- CONFIG ----------------
EDIT_VIDEO = True       # True = edit 65s, False = không edit
MAX_RESOLUTION = 720
API_BASE_URL = "http://localhost:8000"

# ---------------- STORAGE ----------------
uploaded_videos = set()
profile_controllers = {}
file_inputs = {}
http_client = None

# ---------------- UTILS ----------------
def extract_video_id(video_url: str):
    """Trích xuất video_id từ YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtube\.com\/shorts\/([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
            return match.group(1)
    return None

# ---------------- UPLOAD ----------------
async def upload_video_to_tiktok(row, video_file_path, profile_id, channel_id):
    upload_times = {
        'file_upload_time': 0,
        'wait_post_time': 0,
        'post_click_time': 0,
        'reload_time': 0,
        'total_upload_time': 0
    }
    try:
        if row not in profile_controllers or row not in file_inputs:
            print(f"[Row {row}] Profile controller or file input not found")
            return False, None

        controller = profile_controllers[row]
        driver = controller.driver
        upload_start_total = datetime.now()

        # Send file to input
        file_upload_start = datetime.now()
        file_input = file_inputs[row]
        file_input.send_keys(os.path.abspath(video_file_path))
        upload_times['file_upload_time'] = (datetime.now() - file_upload_start).total_seconds()
        print(f"[Row {row}] File uploaded: {video_file_path}")

        # Wait and click post
        wait_post_start = datetime.now()
        def wait_and_click_post():
            btn_selector = 'button[data-e2e="post_video_button"]'
            def is_button_ready(d):
                try:
                    el = d.find_element(By.CSS_SELECTOR, btn_selector)
                    if not el: return None
                    visible = el.is_displayed() and el.size['height'] > 0
                    data_loading = el.get_attribute('data-loading')
                    aria_disabled = el.get_attribute('aria-disabled')
                    enabled = ((data_loading in [None, 'false']) and (aria_disabled in [None, 'false']) and el.is_enabled())
                    return el if visible and enabled else None
                except:
                    return None
            post_button = WebDriverWait(driver, 30, poll_frequency=0.5).until(is_button_ready)
            driver.execute_script("arguments[0].scrollIntoView({ block: 'center' });", post_button)
            post_button.click()
            WebDriverWait(driver, 15).until(lambda d: "tiktokstudio/content" in d.current_url)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, wait_and_click_post)
        upload_times['wait_post_time'] = (datetime.now() - wait_post_start).total_seconds()
        upload_times['total_upload_time'] = (datetime.now() - upload_start_total).total_seconds()

        # Reload upload page
        reload_start = datetime.now()
        def reload_upload_page():
            driver.get("https://www.tiktok.com/tiktokstudio/upload?from=webapp")
            return WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
            )
        new_file_input = await loop.run_in_executor(None, reload_upload_page)
        upload_times['reload_time'] = (datetime.now() - reload_start).total_seconds()
        file_inputs[row] = new_file_input
        return True, upload_times
    except Exception as e:
        print(f"[Row {row}] Upload error: {e}")
        return False, None

# ---------------- HANDLE VIDEO ----------------
async def handle_new_video(row, video_url, profile_id, channel_id):
    video_id = extract_video_id(video_url)
    if video_id and video_id in uploaded_videos:
        print(f"⏭️ [{row}] Video {video_id} already uploaded, skip")
        return

    start_time = datetime.now()
    download_time = 0
    edit_time = 0
    final_file = None

    try:
        print(f"[Row {row}] 📥 Downloading video: {video_url}")
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/download",
                json={
                    "url": video_url,
                    "max_resolution": MAX_RESOLUTION,
                    "progressive_only": False,
                    "edit_65s": EDIT_VIDEO
                }
            )
            response.raise_for_status()
            result = response.json()
        download_time = result.get('download_time', 0)
        edit_time = result.get('edit_time', 0)
        if not result.get('success') or not result.get('file_path'):
            print(f"[Row {row}] ❌ Download failed: {result.get('error','Unknown')}")
            return
        final_file = result['file_path']
        if not os.path.exists(final_file):
            print(f"[Row {row}] ❌ File not found after download")
            return

        # Upload
        if row not in file_inputs:
            print(f"[Row {row}] ❌ File input not ready")
            return
        print(f"[Row {row}] 📤 Uploading to TikTok...")
        upload_success, upload_times = await upload_video_to_tiktok(row, final_file, profile_id, channel_id)
        if upload_success and video_id and upload_times:
            uploaded_videos.add(video_id)
            total_time = (datetime.now() - start_time).total_seconds()
            # Log
            print(f"\n{'='*60}")
            print(f"✅ [{row}] Upload success!")
            print(f"Profile: {profile_id} | Channel: {channel_id}")
            print(f"Video: {video_url}")
            print(f"Download: {download_time:.1f}s | Edit: {edit_time:.1f}s")
            print(f"Upload: {upload_times['total_upload_time']:.1f}s "
                  f"(File: {upload_times['file_upload_time']:.1f}s, Processing: {upload_times['wait_post_time']:.1f}s)")
            print(f"Total: {total_time:.1f}s")
            print(f"{'='*60}\n")
        try:
            if os.path.exists(final_file):
                os.remove(final_file)
        except: pass
    except Exception as e:
        print(f"[Row {row}] ❌ Error: {e}")
        import traceback
        traceback.print_exc()

# ---------------- PROFILE WATCHER ----------------
async def run_profile_watcher(row, profile_id, channel_id, tokens):
    try:
        print(f"[Row {row}] Starting profile: {profile_id}")
        controller = ProfileController(profile_id)
        controller.start_profile()
        controller.connect_selenium()
        controller.open_tiktok()
        file_input = WebDriverWait(controller.driver, 30, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
        )
        print(f"[Row {row}] ✅ File input ready")
        profile_controllers[row] = controller
        file_inputs[row] = file_input

        print(f"[Row {row}] 👀 Watching YouTube channel: {channel_id}")
        start_index = row % len(tokens)
        rotator = TokenRotator(tokens, start_index=start_index)
        async def video_callback(video_url):
            await handle_new_video(row, video_url, profile_id, channel_id)
        await watch_channel(channel_id, rotator, log_callback=lambda msg, link=None: print(f"[Row {row}] {msg}"), video_callback=video_callback)
    except Exception as e:
        print(f"[Row {row}] ❌ Error: {e}")
        import traceback
        traceback.print_exc()

# ---------------- MAIN ----------------
async def main():
    print("="*60)
    print("🚀 REUP TIKTOK - NO UI VERSION (API SERVER)")
    print("="*60)
    tokens = TxtLoader.loads("tokens.txt")
    channels_data = TxtLoader.loads("channels.txt")
    print(f"\n📊 Loaded {len(tokens)} tokens")
    print(f"📊 Loaded {len(channels_data)} channels")
    if len(tokens) < len(channels_data):
        print("⚠️ Tokens < channels, will rotate")

    tasks = []
    for idx, line in enumerate(channels_data):
        parts = line.strip().split("|")
        channel_id = parts[0].strip()
        profile_id = parts[1].strip() if len(parts) == 2 else f"profile_{idx}"
        tasks.append(asyncio.create_task(run_profile_watcher(idx, profile_id, channel_id, tokens)))
    print(f"\n✅ Starting {len(tasks)} watchers...")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
