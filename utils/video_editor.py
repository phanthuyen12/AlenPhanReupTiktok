"""
Video Editor - Cắt video 65s đầu tiên
Sử dụng ffmpeg.exe từ thư mục bin để tương thích khi nén exe
"""
import os
import subprocess
import time

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

def edit_video_to_65s(input_file, output_file=None, duration=65):
    """
    Cắt video thành 65s đầu tiên (hoặc toàn bộ nếu video ngắn hơn)
    Args:
        input_file: Đường dẫn file video input
        output_file: Đường dẫn file output (nếu None thì ghi đè)
        duration: Độ dài video cần cắt (mặc định 65s)
    Returns:
        Đường dẫn file output hoặc None nếu lỗi
    """
    try:
        if not os.path.exists(input_file):
            print(f"❌ File không tồn tại: {input_file}")
            return None
        
        # Kiểm tra độ dài video thực tế (tùy chọn - để tối ưu cho video ngắn)
        # Nếu video ngắn hơn duration, chỉ cần copy file (nhanh hơn)
        try:
            import subprocess as sp
            ffmpeg_path = get_ffmpeg_path()
            probe_cmd = [
                ffmpeg_path, "-i", input_file,
                "-show_entries", "format=duration",
                "-v", "quiet", "-of", "csv=p=0"
            ]
            result = sp.run(probe_cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                video_duration = float(result.stdout.strip())
                # Nếu video ngắn hơn hoặc bằng duration, chỉ cần copy file
                if video_duration <= duration:
                    print(f"📹 Video chỉ có {video_duration:.1f}s, không cần cắt")
                    # Copy file trực tiếp (nhanh nhất)
                    import shutil
                    if output_file is None:
                        base_name = os.path.splitext(input_file)[0]
                        ext = os.path.splitext(input_file)[1]
                        output_file = f"{base_name}_65s{ext}"
                    shutil.copy2(input_file, output_file)
                    print(f"✅ Copy complete (no edit needed) | Size: {os.path.getsize(output_file) / (1024*1024):.2f} MB")
                    return output_file
        except:
            pass  # Nếu không probe được thì cắt bình thường
        
        # Nếu không có output_file, tạo tên mới
        if output_file is None:
            base_name = os.path.splitext(input_file)[0]
            ext = os.path.splitext(input_file)[1]
            output_file = f"{base_name}_65s{ext}"
        
        ffmpeg_path = get_ffmpeg_path()
        
        # Command để cắt video 65s đầu tiên (hoặc toàn bộ nếu ngắn hơn)
        command = [
            ffmpeg_path,
            "-y",  # Overwrite output file
            "-i", input_file,
            "-t", str(duration),  # Cắt 65s đầu tiên (hoặc toàn bộ nếu ngắn hơn)
            "-c", "copy",  # Copy codec để nhanh (không encode lại)
            "-avoid_negative_ts", "make_zero",  # Tránh lỗi timestamp
            output_file
        ]
        
        print(f"✂️ Editing video: {os.path.basename(input_file)} → {os.path.basename(output_file)}")
        start_time = time.perf_counter()
        
        # Chạy ffmpeg
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True
        )
        
        elapsed = time.perf_counter() - start_time
        
        if os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024 * 1024)
            print(f"✅ Edit complete in {elapsed:.1f}s | Size: {size_mb:.2f} MB")
            return output_file
        else:
            print(f"❌ Output file không được tạo: {output_file}")
            return None
            
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
        print(f"❌ FFmpeg error: {error_msg[:200]}")
        return None
    except Exception as e:
        print(f"❌ Edit error: {type(e).__name__} - {e}")
        return None

