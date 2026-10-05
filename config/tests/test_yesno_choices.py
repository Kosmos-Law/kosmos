"""Every boolean input is a Select over the one YESNO_CHOICES. The forms
used to carry their own tuples in three encodings, and the 0/1 one never
pre-selected a stored True (a Select matches on str(value), "True")."""

import re
from pathlib import Path

from django import forms

from config.helpers import YESNO_CHOICES

ROOT = Path(__file__).resolve().parents[2]


def test_a_stored_true_preselects_yes():
    html = forms.Select(choices=YESNO_CHOICES).render("comp", True)

    assert re.search(r'<option value="True" selected>Yes', html)
    assert "No</option>" in html


def test_no_form_defines_its_own_yes_no_tuple():
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "apps").rglob("forms.py")
        if re.search(r'\(\s*(1|True|"True")\s*,\s*"Yes"\s*\)', path.read_text())
    ]
    assert offenders == [
        # Keeps its own label, "No (Administrative)", for the billable select.
        "apps/matters/forms.py",
    ]
