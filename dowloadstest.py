"""
Test script để test download YouTube video
Sử dụng hàm download_youtube_video từ utils/youtube_downloader.py
"""
from utils.youtube_downloader import download_youtube_video
import os

def test_download():
    """Test download YouTube video"""
    
    # Test URL - có thể thay đổi
    test_urls = [
        "https://www.youtube.com/shorts/tw-851JlY8Q",  # YouTube Shorts
        # "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Video thường
    ]
    
    # Thư mục download
    download_path = "Downloads"
    
    print("=" * 60)
    print("🧪 TEST DOWNLOAD YOUTUBE VIDEO")
    print("=" * 60)
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n📹 Test {i}/{len(test_urls)}")
        print(f"URL: {url}")
        print("-" * 60)
        
        # Test với progressive_only=True (nhanh hơn)
        print("\n🔹 Test 1: Progressive stream (max 720p)")
        filepath = download_youtube_video(
            url=url,
            download_path=download_path,
            max_resolution=720,
            progressive_only=True
        )
        
        if filepath and os.path.exists(filepath):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"✅ SUCCESS! File saved: {filepath}")
            print(f"📊 File size: {size_mb:.2f} MB")
        else:
            print("❌ FAILED! File not found")
        
        print("\n" + "=" * 60)
        
        # Test với progressive_only=False (có thể merge audio/video)
        print("\n🔹 Test 2: Adaptive streams (max 720p, allow merge)")
        filepath2 = download_youtube_video(
            url=url,
            download_path=download_path,
            max_resolution=720,
            progressive_only=False
        )
        
        if filepath2 and os.path.exists(filepath2):
            size_mb = os.path.getsize(filepath2) / (1024 * 1024)
            print(f"✅ SUCCESS! File saved: {filepath2}")
            print(f"📊 File size: {size_mb:.2f} MB")
        else:
            print("❌ FAILED! File not found")
        
        print("\n" + "=" * 60)
        
        # Chỉ test 1 URL để tránh download quá nhiều
        break
    
    print("\n✅ Test completed!")
    print(f"📁 Check files in: {os.path.abspath(download_path)}")

if __name__ == "__main__":
    test_download()

