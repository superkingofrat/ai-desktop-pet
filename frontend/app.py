"""PyQt5 desktop application entry point."""
from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from frontend.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI Assistant")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
