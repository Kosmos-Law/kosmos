"""The system prompt of a session: who is asking, which matter, where the
files are, and how to work.

Shorter than the earlier loop's orientation (agent_prompt.py), which
carried a material index and a working set because the model could only
read through tools with a budget. A session's agent has the harness's own
Read, Grep and Glob over the matter folder and reads what it needs; the
prompt tells it the folder's shape and what the Kosmos tools add.
"""

import os

from apps.settings.models import Firm

from .access import has_financial_access, has_research_access
from .agent_tools import courtlistener_configured
from .context import (
    SOURCE_LINKING,
    format_contacts,
    format_matter_overview,
    format_proceedings,
    format_witnesses,
    load_legal_prompt,
)

WORKING_METHOD = """## Working Method

You are working inside Kosmos, the firm's practice system, on one matter, \
for the person named below. Answer as a careful associate would: read \
before you conclude, say what you read, and separate what the record \
shows from what you infer.

- The matter's files are in the working directory. Use Glob to find \
files, Grep to search across them, and Read to read one. Every PDF \
carries a text layer, so Read and Grep see its text. Folder names are \
the firm's own (Evidence, Drafts, Corr, Record, Discovery, Admin, ...).
- The Kosmos tools (mcp__kosmos__*) add what is not in the folder: the \
matter record (parties, proceedings, events, tasks, timeline facts, \
witnesses), synced email, saved highlights, earlier sessions and \
conversations, and the search across all of it. Prefer search_materials \
when you do not know where something is; prefer Grep when you do.
- Cite what you rely on: the file path, the email, the section. Quote \
the record's words where the words matter.
- You cannot write files, run commands or reach the internet, other \
than the research tools when offered. Say so if asked.
"""

RESEARCH_NOTE = """## Legal Research

search_caselaw and read_opinion reach CourtListener. Quote opinions from \
read_opinion, never from memory; give the citation as CourtListener \
reports it. Save an opinion with save_caselaw only when asked.
"""


def folder_shape(path, limit: int = 40) -> str:
    """The matter folder's top two levels, so the agent starts with a map."""
    if not path or not os.path.isdir(path):
        return "No folder is linked to this matter yet, so there are no files to read."
    lines = []
    try:
        for name in sorted(os.listdir(path)):
            if name.startswith("."):
                continue
            full = os.path.join(path, name)
            if os.path.isdir(full):
                try:
                    count = sum(
                        1
                        for entry in os.scandir(full)
                        if not entry.name.startswith(".")
                    )
                except OSError:
                    count = 0
                lines.append(f"- {name}/ ({count} item{'s' if count != 1 else ''})")
            else:
                lines.append(f"- {name}")
            if len(lines) >= limit:
                lines.append("- ...")
                break
    except OSError:
        return "The matter folder could not be listed."
    return "Top level of the matter folder:\n" + "\n".join(lines)


def build_session_system(session, user, folder_path) -> str:
    matter = session.matter
    company = Firm.objects.first()
    jurisdiction = (
        matter.jurisdiction
        or (company.jurisdiction if company else "")
        or "United States common law"
    )
    who = user.get_full_name() or user.username
    parts = [
        load_legal_prompt(jurisdiction=jurisdiction),
        WORKING_METHOD,
        *(
            [RESEARCH_NOTE]
            if has_research_access(user) and courtlistener_configured()
            else []
        ),
        SOURCE_LINKING,
        f"## Current Matter: {matter.name}",
        f"Asking: {who}"
        + (" (may see billing and invoices)" if has_financial_access(user) else ""),
        format_matter_overview(matter),
        "### Contacts\n" + format_contacts(matter),
        "### Witnesses\n" + format_witnesses(matter),
        "### Proceedings\n" + format_proceedings(matter),
        "## Files\n" + folder_shape(folder_path),
    ]
    return "\n\n".join(p for p in parts if p)
