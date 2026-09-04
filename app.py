
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QToolBar
from PySide6.QtGui import QAction
from seq_edit import SequenceEditor
from anim_edit import AnimationEditor
# Only needed for access to command line arguments
import sys

# You need one (and only one) QApplication instance per application.
# Pass in sys.argv to allow command line arguments for your app.
# If you know you won't use command line arguments QApplication([]) works too.
app = QApplication(sys.argv)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AKOS Configurator")
        self.setFixedSize(QSize(1200, 800))
        main_toolbar = QToolBar("Main Toolbar")
        self.addToolBar(main_toolbar)

        button_action = QAction("Open Animation", self)
        button_action.setStatusTip("Open an AKOS directory")
        button_action.triggered.connect(self.open_directory)
        main_toolbar.addAction(button_action)

        seq_action = QAction("Open Sequence", self)
        seq_action.setStatusTip("Open an image sequence directory to color-reduce")
        seq_action.triggered.connect(self.open_sequence_directory)
        main_toolbar.addAction(seq_action)

    def open_sequence_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Sequence Directory"
        )
        if not directory:
            return
        self.setCentralWidget(SequenceEditor(directory))

    def open_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Animation Directory"
        )
        self.setCentralWidget(AnimationEditor(directory))

# Create a Qt widget, which will be our window.
window = MainWindow()
window.show()

app.exec()
