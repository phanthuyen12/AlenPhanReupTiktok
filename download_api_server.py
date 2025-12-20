# download_api_server_async.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
import os
import uuid
from datetime import datetime

from utils.youtube_downloader import download_youtube_video
from utils.video_editor import edit_video_to_65s

app = FastAPI(title="YouTube Download API Async", version="1.1.0")

DOWNLOAD_DIR = os.path.join(os.getcwd(), "Downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Trạng thái download
download_status = {}  # video_id: {"status": "processing|done|error", "file_path": None, "error": None, "download_time": 0, "edit_time": 0}

# Cache video URL -> file_path
video_cache = {}  # url: file_path

# Request body model
class DownloadRequest(BaseModel):
    url: str
    max_resolution: int = 720
    progressive_only: bool = False
    edit_65s: bool = False

# Response model
class DownloadResponse(BaseModel):
    success: bool
    status: str
    video_id: Optional[str] = None
    file_path: Optional[str] = None
    error: Optional[str] = None
    download_time: Optional[float] = None
    edit_time: Optional[float] = None

# Background task
async def background_download(video_url: str, video_id: str, max_resolution: int, progressive_only: bool, edit_65s: bool):
    download_start = datetime.now()
    edit_start = None
    try:
        # Nếu video đã cache, dùng file cũ
        if video_url in video_cache and os.path.exists(video_cache[video_url]):
            final_file = video_cache[video_url]
            download_time = (datetime.now() - download_start).total_seconds()
            edit_time = 0
            download_status[video_id] = {
                "status": "done",
                "file_path": final_file,
                "error": None,
                "download_time": download_time,
                "edit_time": edit_time
            }
            return

        # Download video
        video_file = await asyncio.to_thread(
            download_youtube_video,
            video_url,
            DOWNLOAD_DIR,
            max_resolution,
            progressive_only
        )
        download_time = (datetime.now() - download_start).total_seconds()

        if not video_file or not os.path.exists(video_file):
            download_status[video_id] = {
                "status": "error",
                "file_path": None,
                "error": "Download failed - file not found",
                "download_time": download_time,
                "edit_time": 0
            }
            return

        final_file = video_file
        edit_time = 0

        # Edit video nếu cần
        if edit_65s:
            edit_start = datetime.now()
            edited_file = await asyncio.to_thread(edit_video_to_65s, video_file)
            edit_time = (datetime.now() - edit_start).total_seconds()

            if edited_file and os.path.exists(edited_file):
                final_file = edited_file
                try:
                    os.remove(video_file)
                except:
                    pass

        # Lưu vào cache
        video_cache[video_url] = final_file

        # Cập nhật trạng thái
        download_status[video_id] = {
            "status": "done",
            "file_path": final_file,
            "error": None,
            "download_time": download_time,
            "edit_time": edit_time
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        download_status[video_id] = {
            "status": "error",
            "file_path": None,
            "error": str(e),
            "download_time": (datetime.now() - download_start).total_seconds(),
            "edit_time": 0
        }


@app.get("/")
async def root():
    return {"message": "YouTube Download Async API Server", "status": "running"}


@app.post("/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest):
    """
    Khởi tạo download video, trả JSON ngay.
    Download + edit chạy background.
    """
    video_id = str(uuid.uuid4())
    download_status[video_id] = {"status": "processing", "file_path": None, "error": None, "download_time": 0, "edit_time": 0}

    # Khởi chạy background task
    asyncio.create_task(background_download(
        request.url,
        video_id,
        request.max_resolution,
        request.progressive_only,
        request.edit_65s
    ))

    return DownloadResponse(success=True, status="processing", video_id=video_id)


@app.get("/status/{video_id}", response_model=DownloadResponse)
async def get_status(video_id: str):
    """Check trạng thái download"""
    if video_id not in download_status:
        raise HTTPException(status_code=404, detail="Video ID not found")
    status_info = download_status[video_id]
    return DownloadResponse(
        success=status_info["status"] == "done",
        status=status_info["status"],
        file_path=status_info["file_path"],
        error=status_info["error"],
        download_time=status_info.get("download_time"),
        edit_time=status_info.get("edit_time"),
        video_id=video_id
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "download_api_async"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
