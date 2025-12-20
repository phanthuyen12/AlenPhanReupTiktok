# main.py
from PyQt5.QtWidgets import QApplication, QMainWindow, QHeaderView, QWidget, QCheckBox, QHBoxLayout
from PyQt5 import QtCore, QtWidgets
from ui import Ui_MainWindow   # file UI Qt Designer tạo
from utils import LoadsFile
from utils.tiktok_action import ProfileController
from utils.youtube_downloader import download_youtube_video
from utils.video_editor import edit_video_to_65s
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import asyncio
import qasync
import os
import re
from datetime import datetime
from token_rotator import TokenRotator
from watcher import watch_channel

class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # 🔹 Khởi tạo object để load file
        self.loader = LoadsFile()
        self.checked_rows = set()
        # 🔹 Lưu trữ ProfileController và driver cho mỗi hàng
        self.profile_controllers = {}  # {row: ProfileController}
        # 🔹 Lưu file input cho mỗi hàng
        self.file_inputs = {}  # {row: file_input_element}
        # 🔹 Lưu danh sách video đã upload (chỉ trong session hiện tại)
        self.uploaded_videos = set()  # {video_id}

        # 🔹 Kết nối nút
        self.btnStart.clicked.connect(lambda: asyncio.create_task(self.on_start_clicked()))
        self.btnStop.clicked.connect(self.on_stop_clicked)
        self.btnLoadsToken.clicked.connect(self.loads_file_token)
        self.btnLoadsProfile.clicked.connect(self.loads_file_profile)

        self.setup_table()

    def checkbox_changed(self, state, row):
        """Cập nhật danh sách row checked"""
        if state == QtCore.Qt.Checked:
            self.checked_rows.add(row)
        else:
            self.checked_rows.discard(row)

    def setup_table(self):
        headers = ["Checkout", "Profile", "Channel", "Action", "Status"]
        self.tbData.setColumnCount(len(headers))
        self.tbData.setHorizontalHeaderLabels(headers)
        header = self.tbData.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.tbData.setRowCount(0)

    def loads_file_profile(self):
        file_path = "channels.txt"
        self.data = self.loader.load(file_path)
        self.tbData.setRowCount(0)
        self.checked_rows.clear()

        for i, line in enumerate(self.data):
            parts = line.strip().split("|")
            if len(parts) == 2:
                channel, profile = parts[0].strip(), parts[1].strip()
            else:
                channel, profile = line.strip(), ""

            self.tbData.insertRow(i)

            # Checkbox cell
            chk_widget = QWidget()
            chk_box = QCheckBox()
            chk_box.stateChanged.connect(lambda state, row=i: self.checkbox_changed(state, row))
            layout = QHBoxLayout()
            layout.addWidget(chk_box)
            layout.setAlignment(QtCore.Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            chk_widget.setLayout(layout)
            self.tbData.setCellWidget(i, 0, chk_widget)

            # Profile / Channel / Action / Status
            self.tbData.setItem(i, 1, QtWidgets.QTableWidgetItem(profile))
            self.tbData.setItem(i, 2, QtWidgets.QTableWidgetItem(channel))
            self.tbData.setItem(i, 3, QtWidgets.QTableWidgetItem(""))  # Action
            self.tbData.setItem(i, 4, QtWidgets.QTableWidgetItem(""))  # Status

        self.lbProfile.setText(str(len(self.data)))

    def loads_file_token(self):
        file_path = "tokens.txt"
        self.tokens = self.loader.load(file_path)
        self.lbToken.setText(str(len(self.tokens)))
        print(f"Loaded {len(self.tokens)} tokens")

    async def on_start_clicked(self):
        checked = sorted(self.checked_rows)
        if not checked:
            print("Chưa chọn hàng nào")
            return

        if not hasattr(self, "tokens") or not self.tokens:
            print("No tokens loaded!")
            return

        if len(self.tokens) < len(checked):
            print("⚠️ Số token ít hơn số hàng chọn, sẽ dùng lại theo vòng")

        print("Start clicked")
        tasks = []

        for idx, row in enumerate(checked):
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Opening Profile..."))

            profile_item = self.tbData.item(row, 1)
            channel_item = self.tbData.item(row, 2)
            profile_id = profile_item.text() if profile_item else ""
            channel = channel_item.text() if channel_item else ""

            if not profile_id:
                self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("❌ No Profile ID"))
                self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem("Error"))
                continue

            # Tạo token rotator cho mỗi profile
            start_index = idx % len(self.tokens)
            rotator = TokenRotator(self.tokens, start_index=start_index)
            # Thêm task async - mở Chrome, đợi file input, rồi theo dõi YouTube
            tasks.append(asyncio.create_task(self.run_profile_watcher(row, profile_id, channel, rotator)))

        # Chạy tất cả task đồng thời
        await asyncio.gather(*tasks)

    async def run_profile_watcher(self, row, profile_id, channel, rotator):
        """Mở Chrome bằng Genlogin, đợi file input, sau đó theo dõi YouTube"""
        controller = None
        try:
            # Bước 1: Mở Chrome bằng Genlogin
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Starting Genlogin..."))
            controller = ProfileController(profile_id)
            
            # Chạy trong thread để không block GUI
            await asyncio.to_thread(controller.start_profile)
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Connecting Selenium..."))
            
            await asyncio.to_thread(controller.connect_selenium)
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Opening TikTok Studio..."))
            
            # Bước 2: Mở TikTok Studio và đợi file input
            await asyncio.to_thread(controller.open_tiktok)
            
            # Đợi file input xuất hiện (đảm bảo đã sẵn sàng)
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Waiting for file input..."))
            
            def wait_for_file_input(driver):
                return WebDriverWait(driver, 30, poll_frequency=0.5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
                )
            
            file_input = await asyncio.to_thread(wait_for_file_input, controller.driver)
            
            if file_input:
                self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("✅ File input ready"))
                # Lưu controller và file_input để dùng sau này
                self.profile_controllers[row] = controller
                self.file_inputs[row] = file_input
                
                # Bước 3: Bắt đầu theo dõi YouTube với token rotation
                self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Watching YouTube..."))
                
                def gui_log(msg, video_link=None):
                    # Cập nhật cột Action với log
                    self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem(msg))
                    # Nếu có video mới thì cập nhật cột Status
                    if video_link:
                        self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem(video_link))
                
                # Callback khi có video mới: download và upload
                async def video_callback(video_url):
                    await self.handle_new_video(row, video_url)
                
                await watch_channel(channel, rotator, log_callback=gui_log, video_callback=video_callback)
                self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem("Done"))
            else:
                self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("❌ File input not found"))
                self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem("Error"))
                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"[Row {row}] {error_msg}")
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem(f"❌ {error_msg[:50]}"))
            self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem("Error"))
        finally:
            # Không tự động đóng profile, để người dùng tự quản lý
            pass

    def extract_video_id(self, video_url):
        """Trích xuất video_id từ YouTube URL"""
        # Hỗ trợ nhiều format: watch?v=, shorts/, /v/
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

    async def handle_new_video(self, row, video_url):
        """Xử lý khi có video mới: download → edit (nếu cần) → upload lên TikTok"""
        # Trích xuất video_id để kiểm tra đã upload chưa
        video_id = self.extract_video_id(video_url)
        
        if video_id and video_id in self.uploaded_videos:
            print(f"⏭️ [{row}] Video {video_id} đã được upload, bỏ qua")
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("⏭️ Video đã upload, bỏ qua"))
            return
        
        start_time = datetime.now()
        video_file = None
        final_file = None
        
        try:
            # Lấy thông tin profile và channel
            profile_item = self.tbData.item(row, 1)
            channel_item = self.tbData.item(row, 2)
            profile_id = profile_item.text() if profile_item else "Unknown"
            channel_id = channel_item.text() if channel_item else "Unknown"
            
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("📥 Downloading video..."))
            
            # Download video về thư mục Downloads
            # Tối ưu: dùng progressive_only=True để nhanh hơn (không cần merge)
            download_path = os.path.join(os.getcwd(), "Downloads")
            video_file = await asyncio.to_thread(
                download_youtube_video,
                video_url,
                download_path=download_path,
                max_resolution=720,
                progressive_only=True  # Nhanh hơn, không cần merge audio/video
            )
            
            if not video_file or not os.path.exists(video_file):
                self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("❌ Download failed"))
                return
            
            final_file = video_file
            
            # Kiểm tra radio button: có edit video không?
            need_edit = self.rdEdit65s.isChecked()
            
            if need_edit:
                self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("✂️ Editing video to 65s..."))
                
                # Edit video cắt 65s đầu tiên
                edited_file = await asyncio.to_thread(
                    edit_video_to_65s,
                    video_file
                )
                
                if edited_file and os.path.exists(edited_file):
                    final_file = edited_file
                    # Xóa file gốc sau khi edit xong để tiết kiệm dung lượng
                    try:
                        os.remove(video_file)
                    except:
                        pass
                else:
                    print(f"[Row {row}] Edit failed, using original file")
                    # Nếu edit lỗi thì dùng file gốc
            
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("📤 Uploading to TikTok..."))
            
            # Upload video lên TikTok
            upload_success = await self.upload_video_to_tiktok(row, final_file)
            
            # Chỉ đánh dấu đã upload và log nếu upload thành công
            if upload_success and video_id:
                # Đánh dấu video đã được upload
                self.uploaded_videos.add(video_id)
                
                # Tính thời gian hoàn thành
                end_time = datetime.now()
                elapsed_time = end_time - start_time
                elapsed_str = f"{elapsed_time.total_seconds():.1f}s"
                
                # Log vào txtLog: profile - kênh - videos - thời gian hoàn thành
                log_message = f"{profile_id} | {channel_id} | {video_url} | {elapsed_str}\n"
                self.txtLog.appendPlainText(log_message)
            
            # Xóa file sau khi upload xong (tùy chọn)
            try:
                if os.path.exists(final_file):
                    os.remove(final_file)
            except:
                pass
            
        except Exception as e:
            error_msg = f"Error handling video: {str(e)}"
            print(f"[Row {row}] {error_msg}")
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem(f"❌ {error_msg[:50]}"))
            
            # Cleanup files nếu có lỗi
            for f in [video_file, final_file]:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass

    async def upload_video_to_tiktok(self, row, video_file_path):
        """Upload video lên TikTok Studio và click nút Post
        Returns: True nếu upload thành công, False nếu lỗi"""
        try:
            if row not in self.profile_controllers or row not in self.file_inputs:
                print(f"[Row {row}] Profile controller or file input not found")
                return False
            
            controller = self.profile_controllers[row]
            driver = controller.driver
            
            # Upload file
            def upload_file():
                # Tìm lại file input (có thể đã thay đổi sau khi reload)
                file_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
                )
                file_input.send_keys(os.path.abspath(video_file_path))
                print(f"[Row {row}] File uploaded: {video_file_path}")
            
            await asyncio.to_thread(upload_file)
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("⏳ Waiting for upload..."))
            
            # Đợi nút Post xuất hiện và click
            def wait_and_click_post():
                post_button = WebDriverWait(driver, 120, poll_frequency=1).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-e2e="post_video_button"]'))
                )
                post_button.click()
                print(f"[Row {row}] Post button clicked")
            
            await asyncio.to_thread(wait_and_click_post)
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("✅ Video posted!"))
            
            # Đợi một chút rồi reload trang upload mới
            await asyncio.sleep(3)
            
            def reload_upload_page():
                driver.get("https://www.tiktok.com/tiktokstudio/upload?from=webapp")
                # Đợi file input xuất hiện lại
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
                )
                print(f"[Row {row}] Reloaded upload page")
            
            await asyncio.to_thread(reload_upload_page)
            
            # Cập nhật file_input mới
            def get_new_file_input():
                return WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
                )
            
            new_file_input = await asyncio.to_thread(get_new_file_input)
            self.file_inputs[row] = new_file_input
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("✅ Ready for next video"))
            return True  # Upload thành công
            
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            print(f"[Row {row}] {error_msg}")
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem(f"❌ {error_msg[:50]}"))
            return False  # Upload thất bại

    def on_stop_clicked(self):
        print("Stop clicked")
        for row in self.checked_rows:
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Stopping Profile..."))
            self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem("Stopped"))
            
            # Dừng profile nếu đang chạy
            if row in self.profile_controllers:
                controller = self.profile_controllers[row]
                try:
                    controller.stop_profile()
                    del self.profile_controllers[row]
                except Exception as e:
                    print(f"Error stopping profile {row}: {e}")
            
            # Xóa file_input
            if row in self.file_inputs:
                del self.file_inputs[row]

