import colorsys
import math
import os
import re

from PIL import Image

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QSlider, QToolButton, QVBoxLayout, QWidget,
)

ROOM_PALETTE_PATH = "4roomPalette.bmp"
TRANSPARENT_DEFAULT = "#ffd3ff"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

_PALETTE_CACHE = None


def room_palette():
    global _PALETTE_CACHE
    if _PALETTE_CACHE is None:
        im = Image.open(ROOM_PALETTE_PATH)
        pal = im.getpalette()
        if not pal:
            raise RuntimeError(f"no palette found in {ROOM_PALETTE_PATH}")
        _PALETTE_CACHE = [tuple(pal[i:i + 3]) for i in range(0, len(pal), 3)]
    return _PALETTE_CACHE


def _hsv_cyl(rgb):
    r, g, b = (c / 255.0 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    ang = math.radians(h * 360.0)
    return (s * math.cos(ang), s * math.sin(ang), v)


def _nearest_cyl(rgb, cycands):
    x, y, z = _hsv_cyl(rgb)
    best, best_d = 0, None
    for i, (cx, cy, cz) in enumerate(cycands):
        d = (x - cx) * (x - cx) + (y - cy) * (y - cy) + (z - cz) * (z - cz)
        if best_d is None or d < best_d:
            best, best_d = i, d
    return best


def quantize_frame(img, colors):
    rgba = img.convert("RGBA")
    if not colors:
        return rgba.copy()
    w, h = rgba.size
    src = rgba.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dst = out.load()
    cycands = [_hsv_cyl(c) for c in colors]
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a == 0:
                continue
            dst[x, y] = colors[_nearest_cyl((r, g, b), cycands)] + (255,)
    return out


def paint_transparent(rgba, transparent_rgb):
    rgb = rgba.convert("RGB")
    base = Image.new("RGB", rgba.size, transparent_rgb)
    mask = rgba.getchannel("A")
    return Image.composite(rgb, base, mask)


def natkey(text):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def load_sequence_files(directory):
    if not os.path.isdir(directory):
        return []
    names = [n for n in os.listdir(directory)
             if os.path.splitext(n)[1].lower() in IMAGE_EXTS]
    names.sort(key=natkey)
    return [os.path.join(directory, n) for n in names]


def pil_to_pixmap(img):
    im = img.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    qim = QImage(data, im.size[0], im.size[1], QImage.Format_RGBA8888)
    return QPixmap.fromImage(qim)


def _contrast_color(rgb):
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return "#000" if lum > 140 else "#fff"


class PaletteGrid(QWidget):
    color_clicked = Signal(int)

    def __init__(self):
        super().__init__()
        palette = room_palette()
        grid = QGridLayout()
        grid.setSpacing(2)
        for i, color in enumerate(palette):
            btn = QToolButton()
            btn.setFixedSize(18, 18)
            btn.setStyleSheet(f"background-color: {QColor(*color).name()}; border: 1px solid #333;")
            btn.setToolTip(f"index {i}: {color}")
            btn.clicked.connect(lambda checked, idx=i: self.color_clicked.emit(idx))
            grid.addWidget(btn, i // 16, i % 16)
        grid.setRowStretch(16, 1)
        host = QWidget()
        host.setLayout(grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)
        self.setLayout(lay)


class SlotRow(QWidget):
    slot_clicked = Signal(int)

    def __init__(self):
        super().__init__()
        self.buttons = []
        grid = QGridLayout()
        grid.setSpacing(2)
        for i in range(16):
            btn = QToolButton()
            btn.setFixedSize(24, 24)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self.slot_clicked.emit(idx))
            grid.addWidget(btn, i // 8, i % 8)
            self.buttons.append(btn)
        self.setLayout(grid)

    def set_slots(self, slot_colors, active_index):
        palette = room_palette()
        for i, btn in enumerate(self.buttons):
            idx = slot_colors[i]
            if idx is not None:
                color = QColor(*palette[idx])
                bg = color.name()
                fg = _contrast_color(palette[idx])
            else:
                bg, fg = "#555", "#aaa"
            border = "border: 2px solid #fff;" if i == active_index else "border: 1px solid #333;"
            btn.setStyleSheet(f"background-color: {bg}; color: {fg}; {border}")
            btn.setChecked(i == active_index)
            btn.setToolTip(f"slot {i}: " + (f"palette index {idx}" if idx is not None else "empty"))


class SequenceConfig(QWidget):
    palette_changed = Signal()
    save_requested = Signal()

    def __init__(self):
        super().__init__()
        self.slot_colors = [None] * 16
        self.active_slot = None
        self.transparent_hex = TRANSPARENT_DEFAULT

        trans_row = QHBoxLayout()
        trans_row.addWidget(QLabel("Transparent:"))
        self.trans_swatch = QPushButton()
        self.trans_swatch.setFixedSize(130, 26)
        self.trans_swatch.setToolTip("Pixel color used for transparent (alpha=0) source pixels")
        self.trans_swatch.clicked.connect(self.pick_transparent)
        trans_row.addWidget(self.trans_swatch)
        trans_row.addStretch(1)

        self.slots = SlotRow()
        self.slots.slot_clicked.connect(self.on_slot_clicked)

        self.count_label = QLabel()
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)

        self.palette_grid = PaletteGrid()
        self.palette_grid.color_clicked.connect(self.on_color_clicked)

        self.save_btn = QPushButton("Save Frames...")
        self.save_btn.setToolTip("Reduces all frames and writes them as .png into a chosen folder")
        self.save_btn.clicked.connect(self.save_requested.emit)

        lay = QVBoxLayout()
        lay.addWidget(QLabel("Color Reduction"))
        lay.addLayout(trans_row)
        lay.addSpacing(8)
        lay.addWidget(QLabel("Palette slots (fill as many as you need):"))
        lay.addWidget(self.slots)
        lay.addWidget(self.count_label)
        lay.addWidget(self.hint_label)
        lay.addSpacing(8)
        lay.addWidget(QLabel("4RoomPalette colors:"))
        lay.addWidget(self.palette_grid, 1)
        lay.addWidget(self.save_btn)
        self.setLayout(lay)
        self.refresh_slots()

    def transparent_rgb(self):
        hex_str = self.transparent_hex.lstrip("#")
        return tuple(bytes.fromhex(hex_str))

    def colors(self):
        palette = room_palette()
        return [palette[i] for i in self.slot_colors if i is not None]

    def on_slot_clicked(self, i):
        if self.slot_colors[i] is not None:
            self.slot_colors[i] = None
        else:
            self.active_slot = i
        self.refresh_slots()
        self.palette_changed.emit()

    def on_color_clicked(self, idx):
        if self.active_slot is not None:
            self.slot_colors[self.active_slot] = idx
        else:
            for i in range(16):
                if self.slot_colors[i] is None:
                    self.slot_colors[i] = idx
                    break
        self.refresh_slots()
        self.palette_changed.emit()

    def pick_transparent(self):
        col = QColorDialog.getColor(QColor(self.transparent_hex), self, "Select transparent color")
        if col.isValid():
            self.transparent_hex = col.name()
            self.refresh_slots()
            self.palette_changed.emit()

    def refresh_slots(self):
        rgb = self.transparent_rgb()
        self.trans_swatch.setText(self.transparent_hex)
        self.trans_swatch.setStyleSheet(
            f"background-color: {QColor(*rgb).name()}; color: {_contrast_color(rgb)};"
        )
        self.slots.set_slots(self.slot_colors, self.active_slot)
        used = sum(1 for c in self.slot_colors if c is not None)
        self.count_label.setText(f"colors: {used}/16")
        if self.active_slot is not None:
            self.hint_label.setText(f"Filling slot {self.active_slot}: click a 4RoomPalette color.")
        else:
            self.hint_label.setText("Click a slot to fill it, or click a 4RoomPalette color to auto-fill the first empty slot. Click a filled slot to remove it.")


class SequencePreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(640, 480)
        self.background = QPixmap("room_4_template_background.jpg")
        self.pixmap = None

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.background)
        if self.pixmap is not None:
            x = (self.width() - self.pixmap.width()) // 2
            y = (self.height() - self.pixmap.height()) // 2
            painter.drawPixmap(x, y, self.pixmap)
        painter.end()


class SequenceControls(QWidget):
    frame_change = Signal(int)

    def __init__(self, count):
        super().__init__()
        self.count = count
        self.slider = QSlider(
            Qt.Orientation.Horizontal,
            tickPosition=QSlider.TickPosition.TicksBelow,
            tickInterval=1,
        )
        self.slider.setRange(0, max(count - 1, 0))
        self.slider.setEnabled(count > 0)
        self.slider.valueChanged.connect(lambda v: self.frame_change.emit(v))
        self.label = QLabel()
        lay = QHBoxLayout()
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.label)
        self.setLayout(lay)
        self.set_index(0)

    def set_index(self, i):
        self.slider.blockSignals(True)
        self.slider.setValue(i)
        self.slider.blockSignals(False)
        if self.count == 0:
            self.label.setText("0/0")
        else:
            self.label.setText(f"{i + 1}/{self.count}")


class SequenceEditor(QWidget):
    def __init__(self, directory):
        super().__init__()
        self.paths = load_sequence_files(directory)
        self.images = [None] * len(self.paths)
        self.cache = [None] * len(self.paths)
        self.current = 0

        self.config = SequenceConfig()
        self.config.palette_changed.connect(self.on_config_changed)
        self.config.save_requested.connect(self.save)
        self.config.setFixedWidth(420)

        self.preview = SequencePreview()
        self.controls = SequenceControls(len(self.paths))
        self.controls.frame_change.connect(self.on_frame_change)

        right = QVBoxLayout()
        right.addWidget(self.preview)
        right.addWidget(self.controls)

        main = QHBoxLayout()
        main.addWidget(self.config)
        main.addLayout(right, 1)
        self.setLayout(main)

        if not self.paths:
            QMessageBox.warning(self, "No images", f"No image files found in {directory}")

    def colors(self):
        return self.config.colors()

    def source(self, i):
        if self.images[i] is None:
            self.images[i] = Image.open(self.paths[i]).convert("RGBA")
        return self.images[i]

    def quantized(self, i):
        if self.cache[i] is None:
            colors = self.colors()
            if colors:
                self.cache[i] = quantize_frame(self.source(i), colors)
            else:
                self.cache[i] = self.source(i).copy()
        return self.cache[i]

    def refresh_current(self):
        if not self.paths:
            return
        self.preview.set_pixmap(pil_to_pixmap(self.quantized(self.current)))
        self.controls.set_index(self.current)

    def on_frame_change(self, i):
        self.current = i
        self.refresh_current()

    def on_config_changed(self):
        self.cache = [None] * len(self.paths)
        self.refresh_current()

    def save(self):
        if not self.paths:
            return
        folder = QFileDialog.getExistingDirectory(self, "Select output folder")
        if not folder:
            return
        transparent_rgb = self.config.transparent_rgb()
        for i, path in enumerate(self.paths):
            out = paint_transparent(self.quantized(i), transparent_rgb)
            name = os.path.splitext(os.path.basename(path))[0]
            out.save(os.path.join(folder, f"{name}.png"))
        QMessageBox.information(self, "Saved", f"Saved {len(self.paths)} frames to {folder}")