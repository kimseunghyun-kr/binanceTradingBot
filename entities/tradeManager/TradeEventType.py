from enum import auto, Enum


class TradeEventType(Enum):
    OPEN = auto()  # open new leg
    REDUCE = auto()  # close part of a leg
    CLOSE = auto()  # close remaining size
    MODIFY_SLTP = auto()  # change stop / target
    FUNDING = auto()  # perp funding cash-flow
    LIQUIDATE = auto()  # forced close
    CUSTOM = auto()  # anything else
