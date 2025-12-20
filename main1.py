import sys
from PyQt5.QtWidgets import QApplication
from app import MainWindow

import asyncio
import qasync
def main():
    import sys
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
