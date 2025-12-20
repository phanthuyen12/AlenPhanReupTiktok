"""
Client để gọi API download server
"""
import requests
from typing import Optional, Dict

class DownloadAPIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def download_video(
        self,
        url: str,
        max_resolution: int = 720,
        progressive_only: bool = False,
        edit_65s: bool = False
    ) -> Optional[Dict]:
        """
        Gọi API để download video
        Returns: dict với keys: success, file_path, download_time, edit_time, error
        """
        try:
            response = requests.post(
                f"{self.base_url}/download",
                json={
                    "url": url,
                    "max_resolution": max_resolution,
                    "progressive_only": progressive_only,
                    "edit_65s": edit_65s
                },
                timeout=300  # 5 phút timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ API Error: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
                "download_time": 0,
                "edit_time": 0
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
                "download_time": 0,
                "edit_time": 0
            }

