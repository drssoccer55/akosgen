import struct
import sys
import json
from PIL import Image, ImageColor

class BinaryGen:
    def binary(self) -> bytearray:
        pass


class AKHD(BinaryGen):

    def __init__(self, numFrames, numAnims):
        self.numFrames = numFrames
        self.numAnims = numAnims

    def binary(self) -> bytearray:
        bytez = bytearray()
        bytez += "AKHD".encode()
        bytez += struct.pack(">I", 20) # uint32BE size 4 + 4 + 2*(6)
        bytez += struct.pack("<H", 1) # uint16 versionNumber
        bytez += struct.pack("<H", 32768)  # uint16 costumeFlags
        bytez += struct.pack("<H", self.numAnims)  # uint16 choreCount (num animations I think)
        bytez += struct.pack("<H", self.numFrames)  # uint16 celsCount (num frames)
        bytez += struct.pack("<H", 1)  # uint16 celCompressionCodec
        bytez += struct.pack("<H", 16)  # uint16 layerCount? don't think it gets used
        return bytez


class AKPL(BinaryGen):

    def __init__(self, local_palette: list[int]):
        # 16 color palette where certain numbers are special (0 transparent, 232-237 color changer dark to light (consistent across room 3-4 palettes))
        # how is this implemented? Not 100% on this but it seems like actors get a 256 color palette which probably starts out as the room but there
        # is an opcode to update the actorPaletteColor (SO_PALETTE hits in scriptv72he.cpp in range I expect)
        if len(local_palette) != 16:
            print(f'Local Palette does not have 16 colors! {len(local_palette)}')
            exit(1)
        self.local_palette = local_palette

    def binary(self) -> bytearray:
        bytez = bytearray()
        bytez += "AKPL".encode()
        bytez += struct.pack(">I", 24) # 16 colors plus header plus this 4 bytes
        for i in range(len(self.local_palette)):
            bytez.append(self.local_palette[i])
        return bytez

'''
It looks like RGBS is never used (I put breakpoints different places in engine and never saw it consumed). I will skip
adding RGBS. However, if needed, it looks like it is just 256 triplet coloring values that are probably same as room
palette
'''

class ImagePalette:
    @staticmethod
    def rgb_to_key(color: list[int]) -> str:
        return f'{color[0]},{color[1]},{color[2]}'

    @staticmethod
    def rgb_to_key_tuple(color: tuple[int, int, int]) -> str:
        return ImagePalette.rgb_to_key([color[0], color[1], color[2]])

    def __init__(self, room_palette: Image.Image):
        self.color_map = {}
        self.local_colors = {}
        cur_palette = room_palette.getpalette()
        for i in range(0, len(cur_palette), 3):
            key = ImagePalette.rgb_to_key(cur_palette[i:i + 3])
            self.color_map[key] = int(i / 3)

    def get_room_color(self, key):
        tmp = self.color_map.get(key)
        if tmp not in self.local_colors:
            self.local_colors[tmp] = len(self.local_colors)
        return self.local_colors[tmp]

    def get_16_color_local_palette(self):
        # room color -> local color
        items = self.local_colors.items()
        sorted(items, key=lambda x: x[1])
        items = [x[0] for x in items]
        while len(items) < 16:
            items.append(0)
        return items


class AKCD(BinaryGen):
    def __init__(self, frames:list[Image.Image], palette: ImagePalette):
        self.palette = palette
        self.frames = frames
        self.bytez = bytearray()
        self.offsets = []

    def rle_compression(self):
        '''
        For 16 colors, the color is stored in the first 4 bits, and the rep (repeat) is the next 4 bits. If rep is 0,
        need to check the next full bit for the repeat count.
        '''
        for frame in self.frames:
            rgb_frame = frame.convert('RGB')
            self.offsets.append(len(self.bytez))
            cur_color = self.palette.get_room_color(ImagePalette.rgb_to_key_tuple(rgb_frame.getpixel((0, 0))))
            cur_len = 0
            for i in range(rgb_frame.width):
                for j in range(rgb_frame.height):
                    pix_color = ImagePalette.rgb_to_key_tuple(rgb_frame.getpixel((i, j)))
                    room_color = self.palette.get_room_color(pix_color)
                    if room_color == cur_color:
                        cur_len += 1
                        continue
                    else:
                        # RLE encode last run
                        while cur_len > 255:
                            self.bytez += struct.pack("B", cur_color << 4)
                            self.bytez += struct.pack("B", 255)
                            cur_len -= 255
                        if cur_len > 15:
                            self.bytez += struct.pack("B", cur_color << 4)
                            self.bytez += struct.pack("B", cur_len)
                        else:
                            self.bytez += struct.pack("B", cur_color << 4 | cur_len)
                        # Swap to new color
                        cur_color = room_color
                        cur_len = 1
            # ran out of pixels but encode the last run
            if cur_len > 0:
                while cur_len > 255:
                    self.bytez += struct.pack("B", cur_color << 4)
                    self.bytez += struct.pack("B", 255)
                    cur_len -= 255
                if cur_len > 15:
                    self.bytez += struct.pack("B", cur_color << 4)
                    self.bytez += struct.pack("B", cur_len)
                else:
                    self.bytez += struct.pack("B", cur_color << 4 | cur_len)

    def binary(self) -> bytearray:
        self.rle_compression()
        header = bytearray()
        header += "AKCD".encode()
        header += struct.pack(">I", 8 + len(self.bytez)) # uint32BE 4 header, 4 size, rest is compressed bytes
        header += self.bytez
        return header


class AKCI(BinaryGen):
    def __init__(self, frames: list[Image.Image]):
        self.frames = frames

    def binary(self) -> bytearray:
        bytez = bytearray()
        bytez += "AKCI".encode()
        bytez += struct.pack(">I", 8 + len(self.frames) * 4)  # header plus this 4 bytes plus 4 bytes per frame
        for frame in self.frames:
            bytez += struct.pack("<H", frame.width) # uint16
            bytez += struct.pack("<H", frame.height)  # uint16
        return bytez


class AKOF(BinaryGen):
    def __init__(self, akcd_offsets: list[int]):
        self.akcd_offsets = akcd_offsets

    def binary(self) -> bytearray:
        bytez = bytearray()
        bytez += "AKOF".encode()
        bytez += struct.pack(">I", 8 + len(self.akcd_offsets) * 6)  # header plus this 4 bytes plus 6 bytes per frame
        i = 0
        for offset in self.akcd_offsets:
            bytez += struct.pack("<I", offset)  # uint32
            bytez += struct.pack("<H", i)  # uint16
            i += 4
        return bytez


class AKSQ(BinaryGen):
    def __init__(self, data: dict):
        self.data = data
        self.offsets = []

    def binary(self) -> bytearray:
        bytez = bytearray()
        last_draw = 0
        for anim in self.data["anims"]:
            self.offsets.append(len(bytez))
            for cmd in anim["def"]:
                if "special" in cmd:
                    if cmd["special"] == "AKC_HIDE_ACTOR":
                        bytez += struct.pack("<H", 34496) # uint16 0xC086
                else:
                    last_draw = len(bytez)
                    bytez += struct.pack("<H", 8384) # uint16 0xC020
                    bytez += struct.pack("B", 1) # 1 limb
                    bytez += struct.pack("<h", cmd["offs_x"])  # int16
                    bytez += struct.pack("<h", cmd["offs_y"])  # int16
                    bytez += struct.pack("B", cmd["frame"]) # 1 byte representing frames so capped at 256 frames rn
            bytez += struct.pack("<H", 12480) # uint16 0xC030 AKC_GoToState
            bytez += struct.pack("<H", last_draw)
            bytez += struct.pack("<H", 65472)  # uint16 0xC0FF AKC_ENDSEQ

        header = bytearray()
        header += "AKSQ".encode()
        header += struct.pack(">I", 8 + len(bytez))  # uint32BE 4 header, 4 size, rest is cmds
        header += bytez
        return header


class AKCH(BinaryGen):
    def __init__(self, aksq_offsets: list[int]):
        self.aksq_offsets = aksq_offsets

    def binary(self) -> bytearray:
        bytez = bytearray()
        bytez += "AKCH".encode()
        # uint32BE 4 header, 4 size, 8 bytes empty frame, 4 dirs per anim is 8 bytes and 7 bytes per anim def
        # TODO will probably need to handle dirs better in future
        bytez += struct.pack(">I", 16 + 15 * len(self.aksq_offsets))
        bytez += struct.pack("Q", 0) # unsigned long long (8 bytes) unused
        start = len(self.aksq_offsets) * 8 + 8
        for offset in self.aksq_offsets:
            for i in range(4): # 4 dirs
                bytez += struct.pack("<H", start)
            start += 7
        for offset in self.aksq_offsets:
            bytez += struct.pack("<H", 32768) # uint16 mask for 1 limb
            bytez += struct.pack("B", 6)  # 1 byte mode 6
            bytez += struct.pack("<H", offset)  # uint16 start in AKSQ
            bytez += struct.pack("<H", 0)  # len property unused
        return bytez


class AKOS(BinaryGen):
    def __init__(self, path, data: dict):
        self.path = path
        self.data = data

    def binary(self) -> bytearray:
        frames = []
        for frame in data['frames']:
            frames.append(Image.open(f'{self.path}/{frame}'))

        transparent_color = ImageColor.getcolor(self.data["transparent_color"], "RGB")

        # Get room palette and override color of transparent as specified
        room_palette = Image.open(f'{self.data["room_palette"]}roomPalette.bmp')
        cur_palette = room_palette.getpalette()
        cur_palette[0] = transparent_color[0]
        cur_palette[1] = transparent_color[1]
        cur_palette[2] = transparent_color[2]
        room_palette.putpalette(cur_palette)

        image_palette = ImagePalette(room_palette)

        akhd = AKHD(numFrames=len(frames), numAnims=16).binary()
        akcd = AKCD(frames=frames, palette=image_palette) # Have to run akcd to get the local palette
        akcd_bin = akcd.binary() # generates offsets
        local_palette = image_palette.get_16_color_local_palette()
        akpl = AKPL(local_palette=local_palette).binary()
        akci = AKCI(frames=frames).binary()
        akof = AKOF(akcd.offsets).binary()
        aksq = AKSQ(self.data)
        aksq_bin = aksq.binary()
        akch = AKCH(aksq.offsets).binary()
        total_size = len(akhd) + len(akpl) + len(akcd_bin) + len(akci) + len(akof) + len(aksq_bin) + len(akch)
        bytez = bytearray()
        bytez += "AKOS".encode()
        bytez += struct.pack(">I", total_size + 8)
        bytez += akhd
        bytez += akpl
        bytez += akci
        bytez += akof
        bytez += aksq_bin
        bytez += akch
        bytez += akcd_bin
        return bytez


if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print(f'Usage: {args[0]} <dir>')
        exit(1)

    dir_path = args[1]
    with open(f'{dir_path}/info.json', 'r') as file:
        data = json.load(file)
        print(data)

    with open(f'{data["name"]}.AKOS', 'wb') as file:
        file.write(AKOS(path=dir_path, data=data).binary())
