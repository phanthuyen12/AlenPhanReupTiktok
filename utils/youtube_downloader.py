from pytubefix import YouTube
from pytubefix.exceptions import VideoUnavailable, AgeRestrictedError
import os
import time
import subprocess
import re

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def merge_audio_video(video_file, audio_file, output_file):
    command = [
        "ffmpeg",
        "-y",
        "-i", video_file,
        "-i", audio_file,
        "-c:v", "copy",
        "-c:a", "aac",
        output_file
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Merged into {output_file}")

def download_youtube_video(
    url,
    download_path="Downloads",
    max_resolution=720,
    progressive_only=True
):
    """
    Download YouTube video về thư mục Downloads
    Returns: đường dẫn file đã download hoặc None nếu lỗi
    """
    try:
        start_time = time.perf_counter()

        if not os.path.exists(download_path):
            os.makedirs(download_path)
            print(f"Directory created: {download_path}")

        url = url.replace("/shorts/", "/watch?v=")
        video = YouTube(url)
        title_clean = sanitize_filename(video.title)
        print(f"\nVideo: {video.title}")

        if progressive_only:
            stream = video.streams.filter(progressive=True, file_extension='mp4')\
                                  .order_by('resolution').desc().first()
        else:
            stream = video.streams.filter(file_extension='mp4')\
                                  .order_by('resolution').desc().first()

        if not stream:
            print("No suitable stream found!")
            return None

        res_value = int(stream.resolution.replace("p","")) if stream.resolution else 0
        if res_value > max_resolution:
            lower_streams = [s for s in video.streams.filter(file_extension='mp4') 
                             if s.resolution and int(s.resolution.replace("p","")) <= max_resolution]
            if lower_streams:
                stream = lower_streams[0]
        print(f"Selected resolution: {stream.resolution}")

        if progressive_only or getattr(stream, "is_progressive", False):
            filepath = os.path.join(download_path, f"{title_clean}.mp4")
            stream.download(output_path=download_path, filename=f"{title_clean}.mp4")
            end_time = time.perf_counter()
            elapsed_ms = (end_time - start_time) * 1000
            size_kb = os.path.getsize(filepath)/1024
            print(f"Download complete in {elapsed_ms:.0f} ms | File size: {size_kb:.2f} KB")
            return filepath
        else:
            video_stream = video.streams.filter(only_video=True, file_extension='mp4')\
                                        .order_by('resolution').desc().first()
            audio_stream = video.streams.filter(only_audio=True, file_extension='mp4')\
                                        .order_by('abr').desc().first()
            if not video_stream or not audio_stream:
                print("Cannot find adaptive streams to merge!")
                return None

            video_file = os.path.join(download_path, "video_temp.mp4")
            audio_file = os.path.join(download_path, "audio_temp.mp4")
            output_file = os.path.join(download_path, f"{title_clean}.mp4")

            video_stream.download(output_path=download_path, filename="video_temp.mp4")
            audio_stream.download(output_path=download_path, filename="audio_temp.mp4")

            merge_audio_video(video_file, audio_file, output_file)

            os.remove(video_file)
            os.remove(audio_file)
    
            end_time = time.perf_counter()
            elapsed = end_time - start_time
            seconds = int(elapsed)
            milliseconds = int((elapsed - seconds)*1000)
            size_kb = os.path.getsize(output_file)/1024
            print(f"Download complete in {seconds}s {milliseconds}ms | File size: {size_kb:.2f} KB")
            return output_file

    except AgeRestrictedError:
        print("Video bị giới hạn tuổi.")
        return None
    except VideoUnavailable:
        print("Video không tồn tại hoặc private.")
        return None
    except Exception as e:
        print(f"Lỗi: {type(e).__name__} - {e}")
        return None

