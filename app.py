# main.py
from PyQt5.QtWidgets import QApplication, QMainWindow, QHeaderView, QWidget, QCheckBox, QHBoxLayout
from PyQt5 import QtCore, QtWidgets
from ui import Ui_MainWindow   # file UI Qt Designer tạo
from utils import LoadsFile
import asyncio
import qasync
from token_rotator import TokenRotator
from watcher import watch_channel

class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # 🔹 Khởi tạo object để load file
        self.loader = LoadsFile()
        self.checked_rows = set()

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
        if not hasattr(self, "tokens"):
            print("No tokens loaded!")
            return

        print("Start clicked")
        tasks = []

        for row in self.checked_rows:
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Open Profile"))

            profile_item = self.tbData.item(row, 1)
            channel_item = self.tbData.item(row, 2)
            profile = profile_item.text() if profile_item else ""
            channel = channel_item.text() if channel_item else ""

            # Tạo token rotator cho mỗi profile
            rotator = TokenRotator(self.tokens, start_index=row)
            # Thêm task async
            tasks.append(asyncio.create_task(self.run_watcher(row, channel, rotator)))

        # Chạy tất cả task đồng thời
        await asyncio.gather(*tasks)

    async def run_watcher(self, row, channel, rotator):
        try:
            def gui_log(msg, video_link=None):
                # Cập nhật cột Action với log
                self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem(msg))
                # Nếu có video mới thì cập nhật cột Latest Video
                if video_link:
                    self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem(video_link))

            await watch_channel(channel, rotator, log_callback=gui_log)
            self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem("Done"))
        except Exception as e:
            pass
            # self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem(f"Error: {e}"))

    def on_stop_clicked(self):
        print("Stop clicked")
        for row in self.checked_rows:
            self.tbData.setItem(row, 3, QtWidgets.QTableWidgetItem("Stop Profile"))
            self.tbData.setItem(row, 4, QtWidgets.QTableWidgetItem("Stopped"))

