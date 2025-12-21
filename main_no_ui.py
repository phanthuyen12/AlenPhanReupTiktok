"""
Bản không UI để test tốc độ - Gọi trực tiếp, không có PyQt5 overhead
"""
import asyncio
import os
from datetime import datetime
from loader import TxtLoader
from token_rotator import TokenRotator
from watcher import watch_channel
from utils.tiktok_action import ProfileController
import httpx
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import re

# Cấu hình
EDIT_VIDEO = True  # True = edit 65s, False = không edit
MAX_RESOLUTION = 720

# Lưu trữ
uploaded_videos = set()
profile_controllers = {}
file_inputs = {}
API_BASE_URL = "http://localhost:8000"  # API server URL
http_client = None  # Reuse httpx client để tăng tốc độ

def extract_video_id(video_url):
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

async def upload_video_to_tiktok(row, video_file_path, profile_id, channel_id):
    """Upload video lên TikTok Studio và click nút Post - KHÔNG UI"""
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
        
        # BẮT ĐẦU TÍNH THỜI GIAN UPLOAD (từ lúc upload file đến click post thành công)
        upload_start_total = datetime.now()
        
        # Upload file
        file_upload_start = datetime.now()
        if row not in file_inputs:
            raise Exception("File input not found!")
        
        file_input = file_inputs[row]
        file_input.send_keys(os.path.abspath(video_file_path))
        print(f"[Row {row}] File uploaded: {video_file_path}")
        upload_times['file_upload_time'] = (datetime.now() - file_upload_start).total_seconds()
        
        # Đợi nút Post xuất hiện và click
        wait_post_start = datetime.now()
        
        def wait_and_click_post():
            btn_selector = 'button[data-e2e="post_video_button"]'
            
            def is_button_ready(d):
                try:
                    el = d.find_element(By.CSS_SELECTOR, btn_selector)
                    if not el:
                        return None
                    visible = el.is_displayed() and el.size['height'] > 0
                    data_loading = el.get_attribute('data-loading')
                    aria_disabled = el.get_attribute('aria-disabled')
                    enabled = (
                        (data_loading is None or data_loading == 'false') and
                        (aria_disabled is None or aria_disabled == 'false') and
                        el.is_enabled()
                    )
                    return el if (visible and enabled) else None
                except:
                    return None
            
            post_button = WebDriverWait(driver, 30, poll_frequency=0.5).until(is_button_ready)
            driver.execute_script("arguments[0].scrollIntoView({ block: 'center' });", post_button)
            post_button.click()
            print(f"[Row {row}] Post button clicked")
            WebDriverWait(driver, 15).until(lambda d: "tiktokstudio/content" in d.current_url)
            print(f"[Row {row}] Redirected to content page")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, wait_and_click_post)
        
        # KẾT THÚC TÍNH THỜI GIAN UPLOAD (sau khi redirect thành công)
        upload_end_total = datetime.now()
        upload_times['wait_post_time'] = (datetime.now() - wait_post_start).total_seconds()
        
        # TỔNG THỜI GIAN UPLOAD = từ upload file đến click post thành công (KHÔNG tính reload)
        upload_times['total_upload_time'] = (upload_end_total - upload_start_total).total_seconds()
        
        # Reload trang (KHÔNG tính vào total_upload_time)
        reload_start = datetime.now()
        def reload_upload_page():
            driver.get("https://www.tiktok.com/tiktokstudio/upload?from=webapp")
            file_input = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
            )
            print(f"[Row {row}] Reloaded upload page")
            return file_input
        
        new_file_input = await loop.run_in_executor(None, reload_upload_page)
        upload_times['reload_time'] = (datetime.now() - reload_start).total_seconds()
        file_inputs[row] = new_file_input
        return True, upload_times
        
    except Exception as e:
        print(f"[Row {row}] Upload error: {e}")
        return False, None

async def handle_new_video(row, video_url, profile_id, channel_id):
    """Xử lý khi có video mới - KHÔNG UI, GỌI TRỰC TIẾP"""
    video_id = extract_video_id(video_url)
    
    if video_id and video_id in uploaded_videos:
        print(f"⏭️ [{row}] Video {video_id} đã được upload, bỏ qua")
        return
    
    start_time = datetime.now()
    download_time = 0
    edit_time = 0
    final_file = None
    
    try:
        print(f"[Row {row}] 📥 Downloading video: {video_url}")
        
        # Gọi API TRỰC TIẾP bằng httpx async - REUSE CLIENT để tăng tốc độ
        # Client đã được khởi tạo trong main(), không tạo mới mỗi lần (tiết kiệm ~5s overhead)
        global http_client
        response = await http_client.post(
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
            error_msg = result.get('error', 'Unknown error')
            print(f"[Row {row}] ❌ Download failed: {error_msg}")
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
            # Tính total_time = download + edit + upload (KHÔNG tính reload_time)
            # upload_times['total_upload_time'] đã không bao gồm reload_time
            total_time = download_time + edit_time + upload_times['total_upload_time']
            
            # Log ra console
            print(f"\n{'='*60}")
            print(f"✅ [{row}] Upload thành công!")
            print(f"Profile: {profile_id} | Channel: {channel_id}")
            print(f"Video: {video_url}")
            print(f"Download: {download_time:.1f}s | Edit: {edit_time:.1f}s")
            print(f"Upload: {upload_times['total_upload_time']:.1f}s "
                  f"(File: {upload_times['file_upload_time']:.1f}s, "
                  f"Processing: {upload_times['wait_post_time']:.1f}s)")
            print(f"Total: {total_time:.1f}s (Download + Edit + Upload, không tính reload)")
            print(f"{'='*60}\n")
        
        # Xóa file
        try:
            if os.path.exists(final_file):
                os.remove(final_file)
        except:
            pass
            
    except Exception as e:
        print(f"[Row {row}] ❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def run_profile_watcher(row, profile_id, channel_id, tokens):
    """Mở Chrome bằng Genlogin, đợi file input, sau đó theo dõi YouTube"""
    try:
        print(f"[Row {row}] Starting Genlogin profile: {profile_id}")
        controller = ProfileController(profile_id)
        
        # Bước 1: Start profile
        controller.start_profile()
        print(f"[Row {row}] Profile started")
        
        # Bước 2: Connect Selenium
        controller.connect_selenium()
        print(f"[Row {row}] Connected Selenium")
        
        # Bước 3: Open TikTok Studio
        controller.open_tiktok()
        print(f"[Row {row}] Opened TikTok Studio")
        
        # Đợi file input
        file_input = WebDriverWait(controller.driver, 30, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
        )
        
        print(f"[Row {row}] ✅ File input ready")
        profile_controllers[row] = controller
        file_inputs[row] = file_input
        
        # Bắt đầu theo dõi YouTube
        print(f"[Row {row}] 👀 Watching YouTube channel: {channel_id}")
        
        start_index = row % len(tokens)
        rotator = TokenRotator(tokens, start_index=start_index)
        
        def gui_log(msg, video_link=None):
            print(f"[Row {row}] {msg}")
            if video_link:
                print(f"[Row {row}] Video link: {video_link}")
        
        async def video_callback(video_url):
            await handle_new_video(row, video_url, profile_id, channel_id)
        
        await watch_channel(channel_id, rotator, log_callback=gui_log, video_callback=video_callback)
        
    except Exception as e:
        print(f"[Row {row}] ❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main function - KHÔNG UI - DÙNG API SERVER"""
    print("="*60)
    print("🚀 REUP TIKTOK - NO UI VERSION (API SERVER)")
    print("="*60)
    print("⚠️  Đảm bảo API server đang chạy:")
    print("    uvicorn download_api_server:app --host 0.0.0.0 --port 8000")
    print("="*60)
    
    # Load tokens và channels
    tokens = TxtLoader.loads("tokens.txt")
    channels_data = TxtLoader.loads("channels.txt")
    
    print(f"\n📊 Loaded {len(tokens)} tokens")
    print(f"📊 Loaded {len(channels_data)} channels")
    
    if len(tokens) < len(channels_data):
        print("⚠️ Số token ít hơn số channel, sẽ dùng lại theo vòng")
    
    # Khởi tạo HTTP client một lần để reuse (tiết kiệm ~5s mỗi request)
    global http_client
    http_client = httpx.AsyncClient(
        timeout=300.0,
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )
    print("✅ HTTP client initialized (reusable)")
    
    # Parse channels (format: channel_id|profile_id hoặc chỉ channel_id)
    tasks = []
    for idx, line in enumerate(channels_data):
        parts = line.strip().split("|")
        if len(parts) == 2:
            channel_id, profile_id = parts[0].strip(), parts[1].strip()
        else:
            channel_id, profile_id = line.strip(), f"profile_{idx}"
        
        if not profile_id:
            print(f"⚠️ Row {idx}: No profile ID, skipping")
            continue
        
        print(f"\n[{idx}] Channel: {channel_id} | Profile: {profile_id}")
        tasks.append(asyncio.create_task(run_profile_watcher(idx, profile_id, channel_id, tokens)))
    
    print(f"\n✅ Starting {len(tasks)} watchers...")
    print("="*60)
    
    try:
        # Chạy tất cả đồng thời
        await asyncio.gather(*tasks)
    finally:
        # Đóng http client khi kết thúc
        if http_client is not None:
            await http_client.aclose()
            print("\n✅ HTTP client closed")

if __name__ == "__main__":
    asyncio.run(main())

