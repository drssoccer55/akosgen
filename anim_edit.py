import os

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QComboBox, QFileDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget, QHBoxLayout
from PySide6.QtGui import QImage, QPixmap, QPainter
from akos_gen import AKOS
from akos_schema import Frame

class Animation(QObject):
    frame_change = Signal(int)
    anim_change = Signal(int)
    refresh = Signal()

    def __init__(self):
        super().__init__()
        self.config = {}

    @property
    def frame(self) -> int:
        return self.config.get("frame", 0)

    @frame.setter
    def frame(self, value):
        self.config["frame"] = value
        self.frame_change.emit(value)

    @property
    def anim(self) -> int:
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
        self.typehint = akos.hint()
        for frame in akos_frames:
            if self.akos.data.transparent_color is not None:
                if frame.mode == "RGB":
                    frame.putalpha(255) # Completely opaque
                # do the conversion to transparent pixels here by modifying the frame data in place
                target_rgb = tuple(bytes.fromhex(self.akos.data.transparent_color.lstrip("#")))
                pixels = frame.load()
                for y in range(frame.height):
                    for x in range(frame.width):
                        r, g, b, _ = pixels[x, y]
                        if (r, g, b) == target_rgb:
                            pixels[x, y] = (r, g, b, 0)
                
            im = frame.convert("RGBA")
            data = im.tobytes("raw","RGBA")
            qim = QImage(data, im.size[0], im.size[1], QImage.Format_RGBA8888)
            self.frames.append(QPixmap.fromImage(qim))

        # Hook into animation change events
        animation.anim_change.connect(self.on_data_change)
        animation.frame_change.connect(self.on_data_change)
        animation.refresh.connect(self.on_data_change)

    def paintEvent(self, event):
        """
        Controls the order of layers for drawing. PaintEvent is built into the widget system.
        """
        painter = QPainter(self)
        painter.drawPixmap(0,0, self.background)
        if len(self.frames) > 0:
            selected_anim = self.akos.data.anims[self.animation.anim]
            draw_frames = [x for x in selected_anim.definition if isinstance(x, Frame)]
            selected_frame = draw_frames[self.animation.frame]
            char_pos_x = 320
            char_pos_y = 240
            if self.typehint is not None:
                char_pos_x = self.typehint.x_pos
                char_pos_y = self.typehint.y_pos
            char_pos_x += selected_frame.offs_x
            char_pos_y += selected_frame.offs_y
            painter.drawPixmap(char_pos_x, char_pos_y, self.frames[selected_frame.frame])
        painter.end()

    def on_data_change(self):
        self.update()


class PreviewControls(QWidget):
    def __init__(self, akos: AKOS, animation: Animation):
        super().__init__()
        self.akos = akos
        self.animation = animation
        layout = QVBoxLayout()

        # Frame Slider
        timeline_layout = QHBoxLayout()
        self.timeline = QSlider(
            Qt.Orientation.Horizontal,
            tickPosition=QSlider.TickPosition.TicksBelow,
            tickInterval=1
        )
        self.timeline.valueChanged.connect(self.slider_change)
        self.label = QLabel()
        animation.anim_change.connect(self.on_anim_change)
        timeline_layout.addWidget(self.timeline)
        timeline_layout.addWidget(self.label)
        layout.addLayout(timeline_layout)

        # x pos slider
        x_layout = QHBoxLayout()
        self.x_label = QLabel()
        self.x_pos = QSlider(
            Qt.Orientation.Horizontal,
            tickInterval=1,
            minimum=-480,
            maximum=480
        )
        self.x_pos.valueChanged.connect(self.x_slider_change)
        x_layout.addWidget(self.x_label)
        x_layout.addWidget(self.x_pos)
        layout.addLayout(x_layout)

        # y pos slider
        y_layout = QHBoxLayout()
        self.y_label = QLabel()
        self.y_pos = QSlider(
            Qt.Orientation.Horizontal,
            tickInterval=1,
            minimum=-640,
            maximum=640
        )
        self.y_pos.valueChanged.connect(self.y_slider_change)
        y_layout.addWidget(self.y_label)
        y_layout.addWidget(self.y_pos)
        layout.addLayout(y_layout)

        self.on_anim_change() # Run this manually to set timeline size initially
        self.setLayout(layout)

    def x_slider_update_from_data(self):
        selected_frame = self.draw_frames[self.animation.frame] # Needs to be used after draw frames set!
        self.x_label.setText(f"X: {selected_frame.offs_x}")
        self.x_pos.setSliderPosition(selected_frame.offs_x)

    def x_slider_change(self, value: int):
        self.draw_frames[self.animation.frame].offs_x = value
        self.x_slider_update_from_data()
        self.animation.refresh.emit()

    def y_slider_update_from_data(self):
        selected_frame = self.draw_frames[self.animation.frame] # Needs to be used after draw frames set!
        self.y_label.setText(f"Y: {selected_frame.offs_y}")
        self.y_pos.setSliderPosition(selected_frame.offs_y)

    def y_slider_change(self, value: int):
        self.draw_frames[self.animation.frame].offs_y = value
        self.y_slider_update_from_data()
        self.animation.refresh.emit()

    def slider_change(self, value: int):
        self.animation.frame = value
        self.update_slider_label()
        self.x_slider_update_from_data()
        self.y_slider_update_from_data()

    def on_anim_change(self):
        selected_anim = self.akos.data.anims[self.animation.anim]
        self.draw_frames = [x for x in selected_anim.definition if isinstance(x, Frame)]
        self.animation.frame = 0
        self.update_slider_label()
        self.x_slider_update_from_data()
        self.y_slider_update_from_data()

    def update_slider_label(self):
        num_frames = len(self.draw_frames)
        self.timeline.setRange(0, num_frames - 1)
        self.label.setText(f"{self.animation.frame + 1}/{num_frames}")


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

        # Description if exists
        typehint = self.akos.hint()
        if typehint is not None:
            layout.addWidget(QLabel(typehint.desc))

        # Name editor
        name_config = QHBoxLayout()
        name_config.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit(self.akos.data.name)
        self.name_input.editingFinished.connect(self.on_name_change)
        name_config.addWidget(self.name_input)

        # Animation Picker
        animation_picker = QHBoxLayout()
        animation_picker.addWidget(QLabel("Animation:"))
        animbox = QComboBox()
        animation_picker.addWidget(animbox)
        for (i,anim) in enumerate(akos.data.anims):
            animbox.addItem(str(i))
        animbox.activated.connect(self.anim_pick)

        # Save config button
        self.save_btn = QPushButton("Save Config")
        self.save_btn.setToolTip("Writes updated info.json to a chosen folder")
        self.save_btn.clicked.connect(self.save_config)

        layout.addLayout(name_config)
        layout.addLayout(animation_picker)
        layout.addWidget(self.save_btn)
        self.setLayout(layout)

    def anim_pick(self, index: int):
        self.animation.anim = index

    def on_name_change(self):
        self.akos.data.name = self.name_input.text()

    def save_config(self):
        folder = QFileDialog.getExistingDirectory(self, "Select output folder")
        if not folder:
            return

        file_path = os.path.join(folder, 'info.json')

        with open(file_path, 'w') as file:
            file.write(self.akos.data.model_dump_json(indent=4))
        QMessageBox.information(self, "Saved", f"Saved info.json to {file_path}")

class AnimationEditor(QWidget):
    def __init__(self, directory):
            super().__init__()
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
            main_horizontal_panel = QHBoxLayout()
    
            # Config side
            main_horizontal_panel.addWidget(ConfigWindow(akos, animation))
            main_horizontal_panel.addWidget(anim_panel)
    
            self.setLayout(main_horizontal_panel)
