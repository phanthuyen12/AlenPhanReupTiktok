from pytubefix import YouTube
from pytubefix.exceptions import VideoUnavailable, AgeRestrictedError
import os
import time
import subprocess
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def get_ffmpeg_path():
    """Lấy đường dẫn ffmpeg.exe từ thư mục bin (giống chromedriver)"""
    # Lấy thư mục gốc của project
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    ffmpeg_path = os.path.join(project_root, "bin", "ffmpeg.exe")
    
    # Kiểm tra file tồn tại
    if os.path.exists(ffmpeg_path):
        return ffmpeg_path
    
    # Fallback: thử dùng ffmpeg từ PATH nếu không tìm thấy
    return "ffmpeg"

def merge_audio_video(video_file, audio_file, output_file):
    """Tối ưu merge với ffmpeg - dùng copy codec để nhanh hơn"""
    ffmpeg_path = get_ffmpeg_path()
    command = [
        ffmpeg_path,
        "-y",
        "-i", video_file,
        "-i", audio_file,
        "-c:v", "copy",  # Copy video codec - không encode lại
        "-c:a", "copy",  # Copy audio codec - nhanh hơn aac encode
        "-shortest",  # Dừng khi stream ngắn nhất kết thúc
        output_file
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"Merged into {output_file}")

def download_stream_async(stream, output_path, filename, result_dict, key):
    """Download stream trong thread riêng"""
    try:
        stream.download(output_path=output_path, filename=filename)
        filepath = os.path.join(output_path, filename)
        result_dict[key] = filepath
    except Exception as e:
        result_dict[key] = None
        print(f"❌ Error downloading {key}: {e}")

def try_client(url, client_name):
    """Thử tạo YouTube object với client cụ thể"""
    try:
        video = YouTube(url, client=client_name, use_oauth=False)
        # Test xem có streams không (đảm bảo client work)
        _ = video.streams.filter(file_extension='mp4').first()
        return video, client_name
    except Exception as e:
        return None, client_name

def download_youtube_video(
    url,
    download_path="Downloads",
    max_resolution=720,
    progressive_only=True
):
    """
    Download YouTube video về thư mục Downloads - TỐI ƯU TỐC ĐỘ
    Returns: đường dẫn file đã download hoặc None nếu lỗi
    """
    try:
        start_time = time.perf_counter()

        if not os.path.exists(download_path):
            os.makedirs(download_path)
            print(f"Directory created: {download_path}")

        # Normalize URL: chuyển shorts thành watch?v= và đảm bảo format đúng
        url = url.replace("/shorts/", "/watch?v=")
        # Đảm bảo URL có format đúng: https://www.youtube.com/watch?v=VIDEO_ID
        if "youtube.com" not in url and "youtu.be" not in url:
            print(f"❌ Invalid YouTube URL: {url}")
            return None
        
        # Nếu là youtu.be thì chuyển sang youtube.com/watch?v=
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1].split("?")[0]
            url = f"https://www.youtube.com/watch?v={video_id}"
        
        try:
            # TỐI ƯU: Thử nhiều client cùng lúc, dùng client nào thành công đầu tiên (nhanh nhất)
            # Chạy song song để tìm client nhanh nhất, không phải chờ từng client một
            clients_to_try = ['WEB', 'ANDROID', 'IOS', 'TV']  # Thứ tự ưu tiên: WEB nhanh nhất
            
            video = None
            used_client = None
            
            # Thử nhiều client song song với ThreadPoolExecutor - dùng client nào thành công đầu tiên
            with ThreadPoolExecutor(max_workers=4) as executor:
                # Submit tất cả clients cùng lúc
                future_to_client = {
                    executor.submit(try_client, url, client): client 
                    for client in clients_to_try
                }
                
                # Dùng client nào thành công đầu tiên (race condition - client nào nhanh nhất)
                for future in as_completed(future_to_client):
                    if video is not None:
                        # Đã tìm được client, cancel các task còn lại để tiết kiệm tài nguyên
                        break
                    
                    try:
                        result_video, result_client = future.result()
                        if result_video is not None:
                            video = result_video
                            used_client = result_client
                            # Cancel các task còn lại
                            for f in future_to_client:
                                if f != future and not f.done():
                                    f.cancel()
                            break
                    except Exception:
                        continue
            
            if video is None:
                # Fallback: thử không chỉ định client (để pytubefix tự chọn)
                video = YouTube(url, use_oauth=False)
                used_client = "DEFAULT"
            
            if used_client:
                print(f"⚡ Using client: {used_client}")
        except Exception as e:
            print(f"❌ Error creating YouTube object: {e}")
            print(f"❌ URL: {url}")
            return None
        
        # TỐI ƯU: Lấy title song song với việc tìm stream để tiết kiệm thời gian
        title_clean = sanitize_filename(video.title)
        print(f"\n📥 Video: {video.title}")

        # TỐI ƯU TỐC ĐỘ: Tìm stream một lần duy nhất, không filter nhiều lần
        # Ưu tiên progressive stream (nhanh nhất, không cần merge)
        all_streams = video.streams.filter(file_extension='mp4')
        progressive_streams = [s for s in all_streams if s.is_progressive]
        
        if progressive_streams:
            # Tìm stream có resolution <= max_resolution, ưu tiên cao nhất
            candidates = [s for s in progressive_streams 
                         if s.resolution and int(s.resolution.replace("p", "")) <= max_resolution]
            if candidates:
                # Chọn resolution cao nhất trong giới hạn (tối ưu: dùng max với key function)
                stream = max(candidates, key=lambda x: int(x.resolution.replace("p", "")))
                progressive_only = True
                print(f"✅ Found progressive stream: {stream.resolution}")
            else:
                # Nếu không có stream <= max_resolution, lấy stream thấp nhất
                stream = min(progressive_streams, 
                           key=lambda x: int(x.resolution.replace("p", "")) if x.resolution else 9999)
                progressive_only = True
                print(f"✅ Using progressive stream: {stream.resolution}")
        else:
            # Không có progressive, mới dùng adaptive (chậm hơn)
            print("⚠️ No progressive stream, using adaptive (slower)...")
            progressive_only = False
            # Tối ưu: filter một lần và sort
            adaptive_streams = [s for s in all_streams if not s.is_progressive]
            if adaptive_streams:
                stream = max(adaptive_streams, 
                           key=lambda x: int(x.resolution.replace("p", "")) if x.resolution and x.resolution.replace("p", "").isdigit() else 0)
            else:
                stream = None

        if not stream:
            print("❌ No suitable stream found!")
            return None

        res_value = int(stream.resolution.replace("p", "")) if stream.resolution else 0
        print(f"📊 Selected resolution: {stream.resolution}")

        # Progressive stream - download trực tiếp (NHANH NHẤT)
        if progressive_only or getattr(stream, "is_progressive", False):
            filepath = os.path.join(download_path, f"{title_clean}.mp4")
            print(f"⬇️ Downloading progressive stream...")
            stream.download(output_path=download_path, filename=f"{title_clean}.mp4")
            end_time = time.perf_counter()
            elapsed = end_time - start_time
            size_kb = os.path.getsize(filepath) / 1024
            print(f"✅ Download complete in {elapsed:.1f}s | Size: {size_kb:.2f} KB")
            return filepath
        
        # Adaptive streams - download song song (NHANH HƠN)
        else:
            print(f"⬇️ Downloading adaptive streams (parallel)...")
            
            # TỐI ƯU: Tìm video và audio stream từ all_streams đã filter sẵn
            video_streams = [s for s in all_streams if s.includes_video_track and not s.includes_audio_track]
            audio_streams = [s for s in all_streams if s.includes_audio_track and not s.includes_video_track]
            
            # Chọn video stream <= max_resolution
            video_candidates = [s for s in video_streams 
                              if s.resolution and s.resolution.replace("p", "").isdigit() 
                              and int(s.resolution.replace("p", "")) <= max_resolution]
            if video_candidates:
                video_stream = max(video_candidates, 
                                  key=lambda x: int(x.resolution.replace("p", "")))
            else:
                video_stream = max(video_streams, 
                                  key=lambda x: int(x.resolution.replace("p", "")) if x.resolution and x.resolution.replace("p", "").isdigit() else 0) if video_streams else None
            
            # Chọn audio stream chất lượng tốt nhất (abr cao nhất)
            audio_stream = max(audio_streams, 
                             key=lambda x: int(x.abr.replace("kbps", "")) if x.abr and x.abr.replace("kbps", "").isdigit() else 0) if audio_streams else None
            
            if not video_stream or not audio_stream:
                print("❌ Cannot find adaptive streams to merge!")
                return None

            video_file = os.path.join(download_path, f"video_temp_{int(time.time())}.mp4")
            audio_file = os.path.join(download_path, f"audio_temp_{int(time.time())}.mp4")
            output_file = os.path.join(download_path, f"{title_clean}.mp4")

            # Download song song để tăng tốc độ
            result_dict = {}
            thread1 = threading.Thread(
                target=download_stream_async,
                args=(video_stream, download_path, os.path.basename(video_file), result_dict, "video")
            )
            thread2 = threading.Thread(
                target=download_stream_async,
                args=(audio_stream, download_path, os.path.basename(audio_file), result_dict, "audio")
            )
            
            thread1.start()
            thread2.start()
            thread1.join()
            thread2.join()
            
            if result_dict.get("video") is None or result_dict.get("audio") is None:
                print("❌ Download failed!")
                # Cleanup
                for f in [video_file, audio_file]:
                    if os.path.exists(f):
                        os.remove(f)
                return None
            
            video_file = result_dict["video"]
            audio_file = result_dict["audio"]
            
            print(f"🔗 Merging audio and video...")
            merge_start = time.perf_counter()
            merge_audio_video(video_file, audio_file, output_file)
            merge_time = time.perf_counter() - merge_start
            
            # Cleanup temp files
            try:
                os.remove(video_file)
                os.remove(audio_file)
            except:
                pass
    
            end_time = time.perf_counter()
            elapsed = end_time - start_time
            size_kb = os.path.getsize(output_file) / 1024
            print(f"✅ Download complete in {elapsed:.1f}s (merge: {merge_time:.1f}s) | Size: {size_kb:.2f} KB")
            return output_file

    except AgeRestrictedError:
        print("❌ Video bị giới hạn tuổi.")
        return None
    except VideoUnavailable:
        print("❌ Video không tồn tại hoặc private.")
        return None
    except Exception as e:
        print(f"❌ Lỗi: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return None

