from dataclasses import field, dataclass
from typing import List
import binascii

@dataclass
class Option:
    inst_id: str
    mark_vol: float
    bid_vol: float
    ask_vol: float
    delta: float
    gamma: float
    vega: float
    theta: float
    vol_lv: float