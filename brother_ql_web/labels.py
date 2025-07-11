from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import cast, Literal

from brother_ql import BrotherQLRaster, create_label
from brother_ql.labels import ALL_LABELS, FormFactor, Label
from brother_ql_web.configuration import Configuration
from brother_ql_web import utils
from PIL import Image, ImageDraw, ImageFont


logger = logging.getLogger(__name__)
del logging


@dataclass
class LabelParameters:
    configuration: Configuration

    font_family: str | None = None
    font_style: str | None = None
    text: str = ""
    image: bytes | None = None
    pdf: bytes | None = None
    font_size: int = 100
    label_size: str = "62"
    margin: int = 10
    threshold: int = 70
    align: str = "center"
    vertical_align: str = "center"
    orientation: str = "standard"
    margin_top: int = 24
    margin_bottom: int = 45
    margin_left: int = 35
    margin_right: int = 35
    label_count: int = 1
    # TODO: Not yet taken into account. The number of dots in each direction has to be
    #       doubled. The generator/calculation methods have to be updated accordingly.
    high_quality: bool = False
    # QR code fields
    qr_data: str = ""
    qr_size: int = 120
    qr_x: int = 30
    qr_y: int = 40
    qr_error_correction: str = "M"
    qr_margin: int = 4
    qr_rotation: int = 0

    @property
    def _label(self) -> Label:
        for label in ALL_LABELS:
            if label.identifier == self.label_size:
                return label
        raise LookupError("Unknown label_size")

    @property
    def kind(self) -> FormFactor:
        return self._label.form_factor

    def _scale_margin(self, margin: int) -> int:
        return int(self.font_size * margin / 100.0)

    @property
    def margin_top_scaled(self) -> int:
        return self._scale_margin(self.margin_top)

    @property
    def margin_bottom_scaled(self) -> int:
        return self._scale_margin(self.margin_bottom)

    @property
    def margin_left_scaled(self) -> int:
        return self._scale_margin(self.margin_left)

    @property
    def margin_right_scaled(self) -> int:
        return self._scale_margin(self.margin_right)

    @property
    def fill_color(self) -> tuple[int, int, int]:
        return (255, 0, 0) if "red" in self.label_size else (0, 0, 0)

    @property
    def font_path(self) -> str:
        try:
            if self.font_family is None or self.font_style is None:
                assert self.configuration.label.default_font is not None
                self.font_family = self.configuration.label.default_font.family
                self.font_style = self.configuration.label.default_font.style
            fonts = utils.collect_fonts(self.configuration)
            path = fonts[self.font_family][self.font_style]
        except KeyError:
            raise LookupError("Couldn't find the font & style")
        return path

    @property
    def width_height(self) -> tuple[int, int]:
        width, height = self._label.dots_printable

        if height > width:
            width, height = height, width
        if self.orientation == "rotated":
            height, width = width, height
        return width, height

    @property
    def width(self) -> int:
        return self.width_height[0]

    @property
    def height(self) -> int:
        return self.width_height[1]


def _determine_image_dimensions(
    text: str, image_font: ImageFont.FreeTypeFont, parameters: LabelParameters
) -> tuple[int, int, int, int]:
    image = Image.new("L", (20, 20), "white")
    draw = ImageDraw.Draw(image)

    left, top, right, bottom = draw.multiline_textbbox(
        xy=(0, 0), text=text, font=image_font
    )
    text_width, text_height = (right - left, bottom - top)
    width, height = parameters.width_height
    if parameters.orientation == "standard":
        if parameters.kind in (FormFactor.ENDLESS,):
            height = (
                text_height
                + parameters.margin_top_scaled
                + parameters.margin_bottom_scaled
            )
    elif parameters.orientation == "rotated":
        if parameters.kind in (FormFactor.ENDLESS,):
            width = (
                text_width
                + parameters.margin_left_scaled
                + parameters.margin_right_scaled
            )
    return width, height, text_width, text_height


def _determine_text_offsets(
    height: int,
    width: int,
    text_height: int,
    text_width: int,
    parameters: LabelParameters,
) -> tuple[int, int]:
    # Vertical alignment logic (respects margins)
    if parameters.vertical_align == "top":
        vertical_offset = parameters.margin_top_scaled
    elif parameters.vertical_align == "bottom":
        vertical_offset = height - parameters.margin_bottom_scaled - text_height
    else:  # center
        vertical_offset = parameters.margin_top_scaled + ((height - parameters.margin_top_scaled - parameters.margin_bottom_scaled - text_height) // 2)
    # Horizontal alignment logic (existing)
    if parameters.orientation == "standard":
        if parameters.align == "left":
            horizontal_offset = parameters.margin_left_scaled
        elif parameters.align == "right":
            horizontal_offset = max(width - text_width - parameters.margin_right_scaled, 0)
        else:  # center (default)
            horizontal_offset = max((width - text_width) // 2, parameters.margin_left_scaled)
    elif parameters.orientation == "rotated":
        if parameters.align == "left":
            horizontal_offset = parameters.margin_left_scaled
        elif parameters.align == "right":
            horizontal_offset = max(width - text_width - parameters.margin_right_scaled, 0)
        else:
            horizontal_offset = max((width - text_width) // 2, parameters.margin_left_scaled)
    return horizontal_offset, vertical_offset


def create_label_image(parameters: LabelParameters) -> Image.Image:
    # QR Code rendering
    if parameters.qr_data:
        import qrcode
        from PIL import ImageOps
        qr = qrcode.QRCode(
            version=None,
            error_correction=getattr(qrcode.constants, f'ERROR_CORRECT_{parameters.qr_error_correction.upper()}', qrcode.constants.ERROR_CORRECT_M),
            box_size=10,
            border=parameters.qr_margin,
        )
        qr.add_data(parameters.qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        # Resize QR code to requested size
        qr_img = qr_img.resize((parameters.qr_size, parameters.qr_size), Image.LANCZOS)
        # Rotate if needed
        if parameters.qr_rotation:
            qr_img = qr_img.rotate(parameters.qr_rotation, expand=True, fillcolor="white")
        # Create label image and paste QR code
        width, height = parameters.width, parameters.height
        image = Image.new("RGB", (width, height), "white")
        image.paste(qr_img, (parameters.qr_x, parameters.qr_y))
        return image

    if parameters.image:
        image = Image.open(BytesIO(parameters.image))

        if parameters.configuration.printer.black_and_white_printer:
            image = image.convert('L')
            bw = image.point(lambda x: 255 if x > parameters.threshold * 255 / 100 else 0, mode='1')
            return bw
        else:
            return image

    image_font = ImageFont.truetype(parameters.font_path, parameters.font_size)

    # Workaround for a bug in multiline_textsize()
    # when there are empty lines in the text:
    lines = []
    for line in parameters.text.splitlines(keepends=False):
        if line == "":
            line = " "
        lines.append(line)
    text = "\n".join(lines)

    width, height, text_width, text_height = _determine_image_dimensions(
        text=text, image_font=image_font, parameters=parameters
    )
    offset = _determine_text_offsets(
        width=width,
        height=height,
        text_width=text_width,
        text_height=text_height,
        parameters=parameters,
    )

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    align = cast(Literal["left", "center", "right"], parameters.align)
    draw.multiline_text(
        offset, text, parameters.fill_color, font=image_font, align=align
    )
    return image


def image_to_png_bytes(image: Image.Image) -> bytes:
    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    return image_buffer.read()


def generate_label(
    parameters: LabelParameters,
    configuration: Configuration,
    save_image_to: str | None = None,
) -> BrotherQLRaster:
    image = create_label_image(parameters)
    if save_image_to:
        image.save(save_image_to)

    red: bool = "red" in parameters.label_size
    rotate: int | str = 0
    if parameters.kind == FormFactor.ENDLESS:
        rotate = 0 if parameters.orientation == "standard" else 90
    elif parameters.kind in (FormFactor.DIE_CUT, FormFactor.ROUND_DIE_CUT):
        rotate = "auto"

    qlr = BrotherQLRaster(configuration.printer.model)
    create_label(
        qlr,
        image,
        parameters.label_size,
        red=red,
        threshold=parameters.threshold,
        cut=True,
        rotate=rotate,
        dpi_600=False,
    )

    return qlr


def print_label(
    parameters: LabelParameters,
    qlr: BrotherQLRaster,
    configuration: Configuration,
    backend_class: type,
) -> None:
    backend = backend_class(configuration.printer.printer)
    for i in range(parameters.label_count):
        logger.info("Printing label %d of %d ...", i + 1, parameters.label_count)
        backend.write(qlr.data)
    backend.dispose()
    del backend
