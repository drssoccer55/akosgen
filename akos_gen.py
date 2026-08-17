import struct
import sys
import json
from PIL import Image, ImageColor

# SCUMM v72he AKOS animation opcodes (little-endian uint16)
AKC_DRAWCEL = 0x20C0        # opcode 0xC020
AKC_SETVAR = 0x10C0          # opcode 0xC010
AKC_EMPTYCEL = 0x01C0        # opcode 0xC001
AKC_GOTOSTATE = 0x30C0       # opcode 0xC030
AKC_IFVAREQJUMP_LASTDRAW = 0x70C0  # opcode 0xC070
AKC_HIDEACTOR = 0x86C0       # opcode 0xC086
AKC_ENDSEQ = 0xFFC0          # opcode 0xC0FF

class BinaryGen:
    def binary(self) -> bytearray:
        raise NotImplementedError


class AKHD(BinaryGen):
    """
    The Actor header. Contains information on the number of frames and chores. Frames is the number of images making up the costume.
    Chores is the number of animation offsets.
    """

    def __init__(self, numFrames, numChores):
        self.numFrames = numFrames
        self.numChores = numChores

    def binary(self) -> bytearray:
        bytez = bytearray()
        bytez += "AKHD".encode()
        bytez += struct.pack(">I", 20) # uint32BE size 4 + 4 + 2*(6)
        bytez += struct.pack("<H", 1) # uint16 versionNumber
        bytez += struct.pack("<H", 32768)  # uint16 costumeFlags
        bytez += struct.pack("<H", self.numChores)  # uint16 choreCount (not number of animations, more like animation slots)
        bytez += struct.pack("<H", self.numFrames)  # uint16 celsCount (num frames)
        bytez += struct.pack("<H", 1)  # uint16 celCompressionCodec
        bytez += struct.pack("<H", 16)  # uint16 layerCount? don't think it gets used
        return bytez


class AKPL(BinaryGen):
    """
    The Actor palette. This is a local 16 color palette which links to the colors in the room palette. Ex. 0 is transparent in the
    room palette so a slot in the local palette being 0 would be the transparent color.
    """

    def __init__(self, local_palette: list[int]):
        # 16 color palette where certain numbers are special (0 transparent, 232-237 color changer dark to light (consistent across room 3-4 palettes))
        # how is this implemented? Not 100% on this but it seems like actors get a 256 color palette which probably starts out as the room but there
        # is an opcode to update the actorPaletteColor (SO_PALETTE hits in scriptv72he.cpp in range I expect)
        if len(local_palette) != 16:
            print(f'Local Palette does not have 16 colors! {len(local_palette)}')
            sys.exit(1)
        self.local_palette = local_palette

    def binary(self) -> bytearray:
        bytez = bytearray()
        bytez += "AKPL".encode()
        bytez += struct.pack(">I", 24) # 16 colors plus header plus this 4 bytes
        for color in self.local_palette:
            bytez.append(color)
        return bytez

'''
It looks like RGBS is never used (I put breakpoints different places in engine and never saw it consumed). I will skip
adding RGBS. However, if needed, it looks like it is just 256 triplet coloring values that are probably same as room
palette
'''

class ImagePalette:
    """
    Initialized on the room palette which is an image of 256 colors. When the frames are processed and a new color
    is encountered it will go through this ImagePalette definition and local colors get recorded. This means the AKPL block
    cannot be created until after the AKCD block is processed.
    """
    @staticmethod
    def rgb_to_key(color) -> str:
        return f'{color[0]},{color[1]},{color[2]}'

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
        if len(self.local_colors) > 16:
            print(f'More than 16 local colors found in frame data {len(self.local_colors)}')
            sys.exit(1)
        # room color -> local color
        items = self.local_colors.items()
        # items sorted by order encountered
        sorted_items = sorted(items, key=lambda x: x[1])
        items = [x[0] for x in sorted_items]

        while len(items) < 16:
            items.append(0)
        return items


class AKCD(BinaryGen):
    """
    Not sure what the CD stands for but this contains all the frame data stored compressed with RLE. All frame data is shoved
    into the binary in a giant blob. This class stores the offsets of the images for consumption but the offsets are not stored in
    the AKCD binary.
    """
    def __init__(self, frames:list[Image.Image], palette: ImagePalette):
        self.palette = palette
        self.frames = frames
        self.bytez = bytearray()
        self.offsets = []

    def _encode_run(self, color: int, length: int):
        '''
        For 16 colors, the color is stored in the first 4 bits, and the rep (repeat) is the next 4 bits. If rep is 0,
        need to check the next full bit for the repeat count.
        '''
        while length > 255:
            self.bytez += struct.pack("B", color << 4)
            self.bytez += struct.pack("B", 255)
            length -= 255
        if length > 15:
            self.bytez += struct.pack("B", color << 4)
            self.bytez += struct.pack("B", length)
        else:
            self.bytez += struct.pack("B", color << 4 | length)

    def rle_compression(self):
        for frame in self.frames:
            rgb_frame = frame.convert('RGB')
            self.offsets.append(len(self.bytez))
            cur_color = self.palette.get_room_color(ImagePalette.rgb_to_key(rgb_frame.getpixel((0, 0))))
            cur_len = 0
            for i in range(rgb_frame.width):
                for j in range(rgb_frame.height):
                    pix_color = ImagePalette.rgb_to_key(rgb_frame.getpixel((i, j)))
                    room_color = self.palette.get_room_color(pix_color)
                    if room_color == cur_color:
                        cur_len += 1
                        continue
                    else:
                        self._encode_run(cur_color, cur_len)
                        cur_color = room_color
                        cur_len = 1
            if cur_len > 0:
                self._encode_run(cur_color, cur_len)

    def binary(self) -> bytearray:
        self.rle_compression()
        header = bytearray()
        header += "AKCD".encode()
        header += struct.pack(">I", 8 + len(self.bytez)) # uint32BE 4 header, 4 size, rest is compressed bytes
        header += self.bytez
        return header


class AKCI(BinaryGen):
    """
    Not sure what CI stands for but this just stores the width and height of the frames.
    """
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
    """
    Stores the frame offsets in the AKCD binary
    """
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
    """
    Actor sequence. This is the bytecode for all the animations packed together. An animation is a list of commands.
    For example, a draw command saying which frame to draw and at what offset. There are also a number of special commands that
    interface with the game and can set game data.
    """
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
                    match cmd["special"]:
                        case "AKC_HIDEACTOR":
                            bytez += struct.pack("<H", AKC_HIDEACTOR)
                        case "AKC_SETVAR":
                            bytez += struct.pack("<H", AKC_SETVAR)
                            bytez += struct.pack("<H", cmd["value"])
                            bytez += struct.pack("B", cmd["var"])
                        case "AKC_EMPTYCEL":
                            bytez += struct.pack("<H", AKC_EMPTYCEL)
                        case "AKC_IFVAREQJUMP_LASTDRAW":
                            bytez += struct.pack("<H", AKC_IFVAREQJUMP_LASTDRAW)
                            bytez += struct.pack("<H", last_draw)
                            bytez += struct.pack("<H", cmd["value"])
                            bytez += struct.pack("B", cmd["var"])
                        case _:
                            print(f"Command not supported {cmd['special']} - skipping")
                            continue
                else:
                    last_draw = len(bytez)
                    bytez += struct.pack("<H", AKC_DRAWCEL)
                    bytez += struct.pack("B", 1) # 1 limb
                    bytez += struct.pack("<h", cmd["offs_x"])  # int16
                    bytez += struct.pack("<h", cmd["offs_y"])  # int16
                    bytez += struct.pack("B", cmd["frame"]) # 1 byte representing frames so capped at 256 frames rn
            bytez += struct.pack("<H", AKC_GOTOSTATE)
            bytez += struct.pack("<H", last_draw)
            bytez += struct.pack("<H", AKC_ENDSEQ)

        header = bytearray()
        header += "AKSQ".encode()
        header += struct.pack(">I", 8 + len(bytez))  # uint32BE 4 header, 4 size, rest is cmds
        header += bytez
        return header


class AKCH(BinaryGen):
    """
    Not sure what CH stands for. AKCH is used for animation offsets and needs the AKSQ binary defined first to know
    where the offsets are located. All animations in this project use 1 limb for simplification.
    """
    def __init__(self, aksq_offsets: list[int], data: dict):
        self.aksq_offsets = aksq_offsets
        self.data = data

    def binary(self) -> bytearray:
        bytez = bytearray()
        bytez += "AKCH".encode()
        # uint32BE 4 header, 4 size, 2 bytes per offset def and 7 bytes per anim def
        bytez += struct.pack(">I", 8 + (7 * len(self.aksq_offsets)) + (2 * len(self.data["anim_offsets"])))
        for anim_offset in self.data["anim_offsets"]:
            if anim_offset == -1:
                bytez += struct.pack("<H", 0) # blank
            else:
                bytez += struct.pack("<H", (7 * anim_offset) + (2 * len(self.data["anim_offsets"])))  # definition position

        for offset in self.aksq_offsets:
            bytez += struct.pack("<H", 32768) # uint16 mask for 1 limb
            bytez += struct.pack("B", 6)  # 1 byte mode 6
            bytez += struct.pack("<H", offset)  # uint16 start in AKSQ
            bytez += struct.pack("<H", 0)  # len property unused
        return bytez


class AKOS(BinaryGen):
    """
    The actor costume. This represents an AKOS file.
    """
    def __init__(self, path, data: dict):
        self.path = path
        self.data = data

    def binary(self) -> bytearray:
        frames = []
        for frame in self.data['frames']:
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

        akhd = AKHD(numFrames=len(frames), numChores=len(self.data["anim_offsets"])).binary()
        akcd = AKCD(frames=frames, palette=image_palette) # Have to run akcd to get the local palette
        akcd_bin = akcd.binary() # generates offsets
        local_palette = image_palette.get_16_color_local_palette()
        akpl = AKPL(local_palette=local_palette).binary()
        akci = AKCI(frames=frames).binary()
        akof = AKOF(akcd.offsets).binary()
        aksq = AKSQ(self.data)
        aksq_bin = aksq.binary()
        akch = AKCH(aksq.offsets, self.data).binary()
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
        sys.exit(1)

    dir_path = args[1]
    with open(f'{dir_path}/info.json', 'r') as file:
        data = json.load(file)

    with open(f'{data["name"]}.AKOS', 'wb') as file:
        file.write(AKOS(path=dir_path, data=data).binary())
