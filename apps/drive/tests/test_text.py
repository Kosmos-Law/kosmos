"""The text inside documents, and the search over a folder of them."""

import shutil
import zipfile

import pytest

from apps.drive import text

pytestmark = pytest.mark.django_db

# A two-page PDF with a text stream on each page. Poppler rebuilds the
# cross-reference table, so the offsets need not be exact.
_PDF = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R /Resources << /Font << /F1 7 0 R >> >> >> endobj
4 0 obj << /Length 60 >> stream
BT /F1 12 Tf 20 200 Td (The Lender Parties claim an interest) Tj ET
endstream endobj
5 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >> endobj
6 0 obj << /Length 50 >> stream
BT /F1 12 Tf 20 200 Td (Served on the lender by mail) Tj ET
endstream endobj
7 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
trailer << /Root 1 0 R >>
%%EOF
"""

_ODT_CONTENT = (
    '<?xml version="1.0"?><office:document-content xmlns:text="x" xmlns:office="o">'
    "<office:body><office:text>"
    "<text:h>Motion to Add Lender</text:h>"
    '<text:p>Plaintiff moves to add<text:s text:c="2"/>Rocket &amp; MERS.</text:p>'
    "<text:p>Second<text:line-break/>paragraph.</text:p>"
    "</office:text></office:body></office:document-content>"
)


def _odt(path, content=_ODT_CONTENT):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        archive.writestr("content.xml", content)


@pytest.fixture
def folder(tmp_path, settings):
    settings.FILES_TEXT_CACHE = tmp_path / "cache"
    matter = tmp_path / "Emling"
    (matter / "Record").mkdir(parents=True)
    (matter / "Drafts").mkdir()
    (matter / "Record" / "motion.pdf").write_bytes(_PDF)
    _odt(matter / "Drafts" / "reply.odt")
    (matter / "notes.txt").write_text("call the lender's counsel\nthen file")
    (matter / "Record" / "photo.jpg").write_bytes(b"\xff\xd8 lender")
    (matter / ".hidden.txt").write_text("lender")
    return matter


def test_office_documents_become_paragraphs(folder):
    got = text.extract(folder / "Drafts" / "reply.odt")
    assert (
        got
        == "Motion to Add Lender\nPlaintiff moves to add  Rocket & MERS.\nSecond\nparagraph."
    )


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")
def test_a_pdf_keeps_its_page_breaks(folder):
    got = text.extract(folder / "Record" / "motion.pdf")
    assert "Lender Parties" in got and "by mail" in got
    assert got.index("\f") < got.index("by mail")


def test_the_cache_is_used_while_the_file_is_unchanged(folder, monkeypatch):
    path = folder / "Drafts" / "reply.odt"
    assert "Rocket" in text.text_of(path)
    calls = []
    monkeypatch.setattr(text, "extract", lambda p: calls.append(p) or "fresh")
    assert "Rocket" in text.text_of(path)  # cached
    assert calls == []
    _odt(path, _ODT_CONTENT.replace("Rocket", "Quicken"))
    assert text.text_of(path) == "fresh"  # size changed: extracted again
    assert calls == [path]


def test_search_reports_the_file_the_page_and_the_line(folder):
    result = text.search(folder, "lender")
    files = {hit["file"] for hit in result["hits"]}
    assert "notes.txt" in files and "Drafts/reply.odt" in files
    assert "Record/photo.jpg" not in files and ".hidden.txt" not in files
    if shutil.which("pdftotext"):
        pdf_hits = [h for h in result["hits"] if h["file"] == "Record/motion.pdf"]
        assert [h["page"] for h in pdf_hits] == [1, 2]
    assert result["files_with_hits"] == len(files)
    report = text.format_search(result)
    assert "for 'lender'" in report and "notes.txt" in report
    assert "call the lender's counsel" in report


def test_search_narrows_to_a_subfolder_and_stays_inside_the_matter(folder):
    result = text.search(folder, "lender", subpath="Drafts")
    assert {h["file"] for h in result["hits"]} == {"Drafts/reply.odt"}
    assert "under Drafts" in text.format_search(result)
    assert "inside" in text.search(folder, "x", subpath="../")["error"]
    assert "no folder" in text.search(folder, "x", subpath="Nope")["error"]
    assert "bad pattern" in text.search(folder, "(", regex=True)["error"]
    assert "No hits" in text.format_search(text.search(folder, "zebra"))


def test_search_caps_the_hits_and_says_so(folder):
    (folder / "many.txt").write_text("\n".join(f"lender {i}" for i in range(100)))
    result = text.search(folder, "lender", limit=3, per_file=2)
    assert result["stopped"] is True
    report = text.format_search(result)
    assert "Stopped after" in report and "and 98 more" in report
