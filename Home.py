import sys
import asyncio
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout
)
from PyQt5.QtCore import pyqtSignal, QObject

# ================= SIGNAL BRIDGE =================

class SignalBridge(QObject):
    log_signal = pyqtSignal(str)

bridge = SignalBridge()

# ================= STOP EVENT =================

stop_event = asyncio.Event()

# ================= ASYNC WORK =================

async def async_job(callback):
    callback("▶ Async job started")

    for i in range(1, 101):
        if stop_event.is_set():
            callback("⛔ Async job stopped")
            return

        callback(f"⏳ Step {i}")
        await asyncio.sleep(0.5)

    callback("✅ Async job finished")

def start_async_loop():
    asyncio.run(async_job(bridge.log_signal.emit))

# ================= UI =================

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyQt5 + asyncio START / STOP")
        self.resize(600, 400)

        self.start_btn = QPushButton("▶ Start")
        self.stop_btn = QPushButton("⛔ Stop")
        self.stop_btn.setEnabled(False)

        self.text = QTextEdit()
        self.text.setReadOnly(True)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)

        layout = QVBoxLayout()
        layout.addLayout(btn_layout)
        layout.addWidget(self.text)
        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start_jobs)
        self.stop_btn.clicked.connect(self.stop_jobs)
        bridge.log_signal.connect(self.log)

    def start_jobs(self):
        self.text.clear()
        stop_event.clear()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        t = threading.Thread(
            target=start_async_loop,
            daemon=True
        )
        t.start()

    def stop_jobs(self):
        stop_event.set()
        self.log("⛔ Stop requested")

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def log(self, msg):
        self.text.append(msg)

# ================= RUN APP =================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
