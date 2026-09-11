from pydantic import BaseModel

class TypeHint(BaseModel):
    name: str
    desc: str
    x_pos: int
    y_pos: int

HINTS = {
    "walkup": TypeHint(
        name="walkup",
        desc="Batter walking up to the plate.",
        x_pos=320,
        y_pos=240
    )
}