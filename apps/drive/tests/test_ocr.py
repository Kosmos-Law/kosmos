"""The text-layer check, and OCR in place through the real OCRmyPDF."""

import shutil

import pytest

from apps.drive import ocr

from .conftest import blank_pdf_bytes, text_pdf_bytes


def test_a_born_digital_pdf_has_text(tmp_path):
    path = tmp_path / "brief.pdf"
    path.write_bytes(text_pdf_bytes())
    assert ocr.has_text(path) is True


def test_a_pdf_with_no_text_layer_has_none(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(blank_pdf_bytes(pages=3))
    assert ocr.has_text(path) is False


def test_a_damaged_file_is_unreadable_not_textless(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a pdf at all")
    assert ocr.has_text(path) is None


def test_only_the_first_pages_are_sampled(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(blank_pdf_bytes(pages=10))
    assert ocr.text_chars(path, pages=2) == 0


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_ocr_in_place_adds_a_text_layer_and_keeps_the_path(tmp_path, settings):
    from PIL import Image, ImageDraw, ImageFont

    settings.FILES_OCR_SCRATCH = tmp_path / "scratch"
    settings.FILES_OCR_JOBS = 1
    tree = tmp_path / "Firm"
    tree.mkdir()
    path = tree / "scan.pdf"
    image = Image.new("RGB", (1200, 400), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=64)
    draw.text((60, 80), "KOSMOS WATCHER TEST DOCUMENT", fill="black", font=font)
    draw.text((60, 220), "SCANNED PAGE WITHOUT A TEXT LAYER", fill="black", font=font)
    image.save(path, "PDF", resolution=150)
    assert ocr.has_text(path) is False
    before = path.stat().st_mode

    ocr.ocr_in_place(path)

    assert ocr.has_text(path) is True
    assert path.stat().st_mode == before
    assert not any((tmp_path / "scratch").iterdir())  # nothing left behind
    assert sorted(p.name for p in tree.iterdir()) == ["scan.pdf"]


def test_ocr_failure_leaves_the_original_untouched(tmp_path, settings):
    settings.FILES_OCR_SCRATCH = tmp_path / "scratch"
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a pdf at all")
    with pytest.raises(ocr.OcrError):
        ocr.ocr_in_place(path)
    assert path.read_bytes() == b"not a pdf at all"
