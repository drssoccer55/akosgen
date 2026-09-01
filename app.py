
from PySide6.QtCore import QSize, QObject, Signal, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QMainWindow, QFileDialog, QSlider, QToolBar, QVBoxLayout, QWidget, QHBoxLayout
from PySide6.QtGui import QAction, QImage, QPixmap, QPainter
from akos_gen import AKOS
# Only needed for access to command line arguments
import sys

# You need one (and only one) QApplication instance per application.
# Pass in sys.argv to allow command line arguments for your app.
# If you know you won't use command line arguments QApplication([]) works too.
app = QApplication(sys.argv)

class Animation(QObject):
    frame_change = Signal(int)
    anim_change = Signal(int)

    def __init__(self):
        super().__init__()
        self.config = {}

    @property
    def frame(self):
        return self.config.get("frame", 0)

    @frame.setter
    def frame(self, value):
        self.config["frame"] = value
        self.frame_change.emit(value)

    @property
    def anim(self):
        return self.config.get("anim", 0)

    @anim.setter
    def anim(self, value):
        self.config["anim"] = value
        self.anim_change.emit(value)


class PreviewWidget(QWidget):
    def __init__(self, akos: AKOS, animation: Animation):
        super().__init__()
        self.setFixedSize(640, 480) # Match resolution of backyard baseball game
        self.background = QPixmap('room_4_template_background.jpg')
        self.animation = animation
        self.akos = akos
        akos_frames = akos.frames()
        self.frames = []
        for frame in akos_frames:
            im = frame.convert("RGBA")
            data = im.tobytes("raw","RGBA")
            qim = QImage(data, im.size[0], im.size[1], QImage.Format_RGBA8888)
            self.frames.append(QPixmap.fromImage(qim))

        # Hook into animation change events
        animation.anim_change.connect(self.on_data_change)
        animation.frame_change.connect(self.on_data_change)

    def paintEvent(self, event):
        """
        Controls the order of layers for drawing. PaintEvent is built into the widget system.
        """
        painter = QPainter(self)
        painter.drawPixmap(0,0, self.background)
        if len(self.frames) > 0:
            selected_anim = self.akos.anims[self.animation.anim]
            draw_frames = [x for x in selected_anim["def"] if x.get("frame", None) is not None]
            selected_frame = draw_frames[self.animation.frame]
            painter.drawPixmap(0,0, self.frames[selected_frame["frame"]])
        painter.end()

    def on_data_change(self):
        self.update()


class PreviewControls(QWidget):
    def __init__(self, akos: AKOS, animation: Animation):
        super().__init__()
        self.akos = akos
        self.animation = animation
        self.frame = 0
        layout = QVBoxLayout()

        # Slider
        self.timeline = QSlider(
            Qt.Orientation.Horizontal,
            tickPosition=QSlider.TickPosition.TicksBelow,
            tickInterval=1
        )
        self.timeline.valueChanged.connect(self.slider_change)
        animation.anim_change.connect(self.on_anim_change)
        self.on_anim_change() # Run this manually to set timeline size initially
        layout.addWidget(self.timeline)
        self.setLayout(layout)

    def slider_change(self, value: int):
        self.animation.frame = value

    def on_anim_change(self):
        selected_anim = self.akos.anims[self.animation.anim]
        draw_frames = [x for x in selected_anim["def"] if x.get("frame", None) is not None]
        num_frames = len(draw_frames)
        self.frame = 0
        self.timeline.setRange(0, num_frames - 1)

class ConfigWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """
    def __init__(self, akos: AKOS, animation: Animation):
        super().__init__()
        self.akos = akos
        self.animation = animation
        layout = QVBoxLayout() # Vertical column of configuration

        # Name editor
        name_config = QHBoxLayout()
        name_config.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit(self.akos["name"])
        name_config.addWidget(self.name_input)

        # Animation Picker
        animation_picker = QHBoxLayout()
        animation_picker.addWidget(QLabel("Animation:"))
        animbox = QComboBox()
        animation_picker.addWidget(animbox)
        for (i,anim) in enumerate(akos.anims):
            animbox.addItem(str(i))
        animbox.currentIndexChanged.connect(self.anim_pick)

        layout.addLayout(name_config)
        layout.addLayout(animation_picker)
        self.setLayout(layout)

    def anim_pick(self, index: int):
        self.animation.anim = index


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

    def open_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Animation Directory"
        )
        # Attempt to create an animation window with the directory
        akos = AKOS(path=directory)
        animation = Animation()

        # Animation Preview side
        anim_panel = QWidget()
        anim_layout = QVBoxLayout()
        anim_layout.addWidget(PreviewWidget(akos, animation))
        anim_layout.addWidget(PreviewControls(akos, animation))
        anim_panel.setLayout(anim_layout)

        # Widget when AKOS is selected
        main_widget = QWidget()
        main_horizontal_panel = QHBoxLayout()

        # Config side
        main_horizontal_panel.addWidget(ConfigWindow(akos, animation))
        main_horizontal_panel.addWidget(anim_panel)

        main_widget.setLayout(main_horizontal_panel)
        self.setCentralWidget(main_widget)

# Create a Qt widget, which will be our window.
window = MainWindow()
window.show()

app.exec()
