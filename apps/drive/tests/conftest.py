"""A small Firm tree on disk, and the users who look at it."""

from io import BytesIO

import pytest
from django.test import Client
from pypdf import PdfWriter

from apps.accounts.models import CustomUser
from apps.matters.models import Matter
from apps.settings.models import Firm

MATTER_FOLDERS = (
    "Matters - Open/Smith v Jones",
    "Matters - Open/Doe v Roe",
    "Matters - Open/Anderson Collection",
    "Matters - Pending/New Intake",
)


def text_pdf_bytes(text="This page carries a real text layer for the watcher to find."):
    """A one-page PDF with ``text`` drawn in Helvetica, built by hand so the
    test needs no PDF generator."""
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        None,  # the content stream, filled in below
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    objects[3] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
    out = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def blank_pdf_bytes(pages=1):
    """A PDF with no text at all, as a scanner without OCR would produce
    (minus the picture)."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def firm_root(tmp_path, settings):
    root = tmp_path / "Firm"
    for rel in MATTER_FOLDERS:
        (root / rel).mkdir(parents=True)
    (root / "Matters - Open" / "0 Archive").mkdir()
    (root / "Matters - Closed" / "2020-2022").mkdir(parents=True)
    (root / ".dropbox.cache").mkdir()
    settings.DROPBOX_FIRM_ROOT = root
    settings.DROPBOX_MATTER_ROOTS = ["Matters - Open", "Matters - Pending"]
    settings.DROPBOX_OCR_EXCLUDE = ["Matters - Closed"]
    settings.FILES_OCR_SCRATCH = tmp_path / "scratch"
    return root


@pytest.fixture(autouse=True)
def company(db):
    return Firm.objects.create(name="Test Firm LLC")


@pytest.fixture
def admin_user():
    user = CustomUser.objects.create(
        username="admin", email="admin@example.com", role="ADMIN"
    )
    user.set_password("pw")
    user.save()
    return user


@pytest.fixture
def admin_client(admin_user):
    client = Client()
    client.force_login(admin_user)
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture
def restricted_user():
    user = CustomUser.objects.create(
        username="restricted", email="restricted@example.com", perm_all_matters=False
    )
    user.set_password("pw")
    user.save()
    return user


@pytest.fixture
def restricted_client(restricted_user):
    client = Client()
    client.force_login(restricted_user)
    client.get("/dash/")
    return client


@pytest.fixture
def matter(db):
    return Matter.objects.create(name="Smith v Jones", status="Open")


@pytest.fixture
def matter2(db):
    return Matter.objects.create(name="Doe v Roe", status="Open")
