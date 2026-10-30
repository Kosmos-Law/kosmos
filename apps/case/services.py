"""The case builder's public surface for the apps that sit on top of it.

Everything another app needs from the case app is imported from here, from
or from apps.case.models; the subpackages are
private, and the import-linter contracts in pyproject.toml hold that line.
What is listed here is what a later extraction of the case builder into its
own package would have to keep.
"""

from apps.case.documents.mbox import (
    EmailMetadata,
    extract_last_name,
    generate_email_description,
    generate_email_pdf,
    parse_email_address,
)
from apps.case.documents.tasks import (
    extract_existing_text,
    process_document_ocr,
    sanitize_text,
)
from apps.case.semantic import (
    register_kind as register_semantic_kind,
    semantic_entries,
)
from apps.case.tabs import (
    Tab,
    register as register_tab,
)
from apps.case.views import get_matter_from_url, get_session_key, set_last_tab

# Task paths for django-q's async_task.
PROCESS_DOCUMENT_OCR_TASK = "apps.case.documents.tasks.process_document_ocr"
GENERATE_DOCUMENT_SUMMARY_TASK = "apps.case.documents.tasks.generate_document_summary"

__all__ = [
    "EmailMetadata",
    "GENERATE_DOCUMENT_SUMMARY_TASK",
    "PROCESS_DOCUMENT_OCR_TASK",
    "Tab",
    "extract_existing_text",
    "extract_last_name",
    "generate_email_description",
    "generate_email_pdf",
    "get_matter_from_url",
    "get_session_key",
    "parse_email_address",
    "process_document_ocr",
    "register_semantic_kind",
    "register_tab",
    "sanitize_text",
    "semantic_entries",
    "set_last_tab",
]
