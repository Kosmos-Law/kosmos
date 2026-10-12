"""The firm logo's derived facts, worked out once at upload.

A logo drawn in one colour on a transparent ground is a shape, not a
picture: the themed pages repaint it in their own text colour, and the
invoice PDF takes a near-black copy made here. Any other logo (several
colours, or art on a solid ground) is shown as uploaded everywhere.
"""

from io import BytesIO
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from PIL import Image, ImageStat

# Pixels at least this opaque count as the logo's ink. The faint edge of
# anti-aliasing is left out: exporters bleed the ground's colour into it.
INK_ALPHA = 128
# How far each RGB channel may spread across the ink and still be one
# colour: room for JPEG-style noise and colour bleed, not for a second hue.
ONE_COLOUR_SPREAD = 24
# The PDF copy's ink: near-black, for paper.
PRINT_INK = (26, 26, 26)


def is_one_colour(image):
    """True when the image is one colour on a ground with transparency."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] == 255:
        return False  # opaque throughout: art on a solid ground
    ink = alpha.point(lambda a: 255 if a >= INK_ALPHA else 0)
    if not ink.getbbox():
        return False  # nothing visible
    for channel in rgba.convert("RGB").split():
        # Fill the transparent ground with the ink's mean, which lies
        # inside the ink's own range, so the extrema are the ink's.
        mean = round(ImageStat.Stat(channel, ink).mean[0])
        inked = Image.composite(channel, Image.new("L", channel.size, mean), ink)
        low, high = inked.getextrema()
        if high - low > ONE_COLOUR_SPREAD:
            return False
    return True


def print_copy(image):
    """The image's shape in PRINT_INK, as PNG bytes."""
    rgba = image.convert("RGBA")
    out = Image.new("RGBA", rgba.size, PRINT_INK)
    out.putalpha(rgba.getchannel("A"))
    buffer = BytesIO()
    out.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def refresh_logo_facts(firm):
    """Set firm.logo_one_colour and firm.logo_print from firm.logo, and
    save. Called whenever the logo changes; the old print copy goes."""
    if firm.logo_print:
        firm.logo_print.delete(save=False)
    firm.logo_one_colour = False
    if firm.logo:
        with firm.logo.open("rb") as f:
            image = Image.open(f)
            image.load()
        if is_one_colour(image):
            firm.logo_one_colour = True
            stem = PurePosixPath(firm.logo.name).stem
            firm.logo_print.save(
                f"{stem}-print.png", ContentFile(print_copy(image)), save=False
            )
    firm.save(update_fields=["logo_one_colour", "logo_print"])
