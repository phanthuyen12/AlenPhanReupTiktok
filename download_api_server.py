"""
FastAPI Server để download YouTube video - Tách riêng để tăng tốc độ
Chạy server: uvicorn download_api_server:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from utils.youtube_downloader import download_youtube_video
from utils.video_editor import edit_video_to_65s
import os
import asyncio
from typing import Optional
import sys

app = FastAPI(title="YouTube Download API", version="1.0.0")

class DownloadRequest(BaseModel):
    url: str
    max_resolution: int = 720
    progressive_only: bool = False
    edit_65s: bool = False  # Có edit 65s không

class DownloadResponse(BaseModel):
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    download_time: Optional[float] = None
    edit_time: Optional[float] = None

@app.get("/")
async def root():
    return {"message": "YouTube Download API Server", "status": "running"}

@app.post("/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest):
    """
    Download YouTube video và trả về đường dẫn file
    Có thể edit 65s nếu cần
    GỌI TRỰC TIẾP để tối ưu tốc độ (giống dowloadstest.py)
    """
    from datetime import datetime
    
    try:
        download_path = os.path.join(os.getcwd(), "Downloads")
        
        # Download video - GỌI TRỰC TIẾP (nhanh nhất, giống dowloadstest.py)
        # Dùng asyncio.to_thread() để không block event loop nhưng vẫn nhanh
        download_start = datetime.now()
        
        # Python 3.9+: dùng to_thread (nhanh hơn), fallback về run_in_executor
        if sys.version_info >= (3, 9):
            video_file = await asyncio.to_thread(
                download_youtube_video,
                request.url,
                download_path,
                request.max_resolution,
                request.progressive_only
            )
        else:
            loop = asyncio.get_event_loop()
            video_file = await loop.run_in_executor(
                None,
                download_youtube_video,
                request.url,
                download_path,
                request.max_resolution,
                request.progressive_only
            )
        
        download_time = (datetime.now() - download_start).total_seconds()
        
        if not video_file or not os.path.exists(video_file):
            return DownloadResponse(
                success=False,
                error="Download failed - file not found",
                download_time=download_time
            )
        
        final_file = video_file
        edit_time = 0
        
        # Edit nếu cần - GỌI TRỰC TIẾP (giống dowloadstest.py)
        if request.edit_65s:
            edit_start = datetime.now()
            
            # Python 3.9+: dùng to_thread, fallback về run_in_executor
            if sys.version_info >= (3, 9):
                edited_file = await asyncio.to_thread(edit_video_to_65s, video_file)
            else:
                loop = asyncio.get_event_loop()
                edited_file = await loop.run_in_executor(None, edit_video_to_65s, video_file)
            
            edit_time = (datetime.now() - edit_start).total_seconds()
            
            if edited_file and os.path.exists(edited_file):
                final_file = edited_file
                # Xóa file gốc
                try:
                    os.remove(video_file)
                except:
                    pass
            else:
                print("Edit failed, using original file")
        
        # Trả về đường dẫn file tuyệt đối
        absolute_path = os.path.abspath(final_file)
        
        return DownloadResponse(
            success=True,
            file_path=absolute_path,
            download_time=download_time,
            edit_time=edit_time
        )
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return DownloadResponse(
            success=False,
            error=error_msg,
            download_time=0,
            edit_time=0
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "download_api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

