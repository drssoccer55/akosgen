from pydantic import BaseModel

class Frame(BaseModel):
    frame: int
    offs_x: int
    offs_y: int

class Special(BaseModel):
    special: str
    var: int | None = None
    value : int | None = None

class AnimDef(BaseModel):
    definition: list[Frame | Special]

class AkosSchema(BaseModel):
    name: str
    frames: list[str]
    room_palette: int
    anims: list[AnimDef]
    anim_offsets: list[int]
    transparent_color: str | None = None
    type_hint: str | None = None