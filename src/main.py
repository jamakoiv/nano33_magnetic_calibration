import sys
import logging
import argparse

from PySide6.QtWidgets import QApplication
from gui import MainWindow

parser = argparse.ArgumentParser(description="")
parser.add_argument(
    "-v", "--verbose", action="count", default=0, help="Set program output level"
)
args = parser.parse_args()

verbosityLevels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
logging.basicConfig(level=verbosityLevels[args.verbose])
log = logging.getLogger(__name__)

# INFO: For now we will use 'info' since matplotlib outputs a lot of stuff at debug-level.
log.info("Program started with arguments: " + str(args))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # breakpoint()
    sys.exit(app.exec())
