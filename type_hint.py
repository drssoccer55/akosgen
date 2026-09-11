from pydantic import BaseModel

class TypeHint(BaseModel):
    name: str
    desc: str
    x_pos: int
    y_pos: int

'''
IMPORTANT: Actors in game go from Y -100 to 380 for some reason. So add 100 to shift to 0 to 480
'''
HINTS = {
    "walkup": TypeHint(
        name="walkup",
        desc="Batter walking up to the plate.",
        x_pos=320,
        y_pos=308
    )
}