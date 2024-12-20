from brother_ql.helpers import ElementsManager as ElementsManager
from enum import IntEnum
from typing import Any

class FormFactor(IntEnum):
    DIE_CUT = 1
    ENDLESS = 2
    ROUND_DIE_CUT = 3
    PTOUCH_ENDLESS = 4

class Color(IntEnum):
    BLACK_WHITE = 0
    BLACK_RED_WHITE = 1

class Label:
    identifier: str
    tape_size: tuple[int, int]
    form_factor: FormFactor
    dots_total: tuple[int, int]
    dots_printable: tuple[int, int]
    offset_r: int
    feed_margin: int
    restricted_to_models: list[str]
    color: Color
    def works_with_model(self, model: str) -> bool: ...
    @property
    def name(self) -> str: ...
    def __init__(
        self,
        identifier: str,
        tape_size: tuple[int, int],
        form_factor: FormFactor,
        dots_total: tuple[int, int],
        dots_printable: tuple[int, int],
        offset_r: int,
        feed_margin: int,
        restricted_to_models: list[str],
        color: Color,
    ) -> None: ...
    def __lt__(self, other: Any) -> bool: ...
    def __le__(self, other: Any) -> bool: ...
    def __gt__(self, other: Any) -> bool: ...
    def __ge__(self, other: Any) -> bool: ...

ALL_LABELS: tuple[Label]

class LabelsManager(ElementsManager):
    DEFAULT_ELEMENTS: tuple[Label]
    ELEMENT_NAME: str
