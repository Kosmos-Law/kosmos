"""What is left of citation vetting: the reader of its stored results.

The vetting job (a fast-tier check of each case citation against the
opinion text) ran after every answer of the retired matter chat; its
results live on ``Message.verified_citations`` and the archive still
shows them (citation_extras, the vetting modal). Nothing writes them now.
"""


def has_pending_vetting(citations: list) -> bool:
    """True if any case citation is still marked as being vetted."""
    for entry in citations or []:
        if entry.get("type") not in (None, "case"):
            continue
        vetting = entry.get("vetting")
        if isinstance(vetting, dict) and vetting.get("status") == "pending":
            return True
    return False
