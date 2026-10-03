"""Kosmos Drafting Companion: AI edits land in the open document, live.

Runs inside LibreOffice Writer (installed as an .oxt downloaded from Kosmos,
which bakes the server URL and the user's token into config.json). "Kosmos >
Connect to drafting session" pairs the front document with its draft link in
Kosmos by file name (asking which one when different files share the name); a
background thread then polls the server every few seconds, applies queued
edit rounds to the live document as tracked changes attributed to "Kosmos
AI", reports each outcome, and pushes the document back (as ODT bytes) so
the AI keeps reading what you see, including your own hand edits.

Before applying a round the extension claims it from the server, which
refuses when the chat has already given up waiting and told the user the
edits were not applied. A refused round is left alone, so the chat and the
document cannot disagree about it.

The edit operations and their semantics are identical to the server's
headless applier (apps/drive/uno_driver.py): replace, delete_paragraph,
insert_after. A round is wrapped in one undo context; if any edit fails the
whole round is undone, so a round either fully applies or leaves the
document untouched (and it is a single Ctrl+Z for the user either way).
"""

import base64
import json
import os
import tempfile
import threading
import traceback
import urllib.error
import urllib.request

import uno
import unohelper
from com.sun.star.lang import DisposedException
from com.sun.star.task import XJobExecutor

POLL_SECONDS = 2.5
# Poll cycles between document pushes when idle (~30 s), so hand edits keep
# flowing back to the AI's context without a round trip per keystroke.
PUSH_EVERY_CYCLES = 12
HTTP_TIMEOUT = 20
AI_AUTHOR = "Kosmos AI"


class CompanionError(Exception):
    def __init__(self, message, edit_index=None):
        super().__init__(message)
        self.edit_index = edit_index


def _prop(name, value):
    from com.sun.star.beans import PropertyValue

    prop = PropertyValue()
    prop.Name = name
    prop.Value = value
    return prop


def _read_config():
    path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_config():
    config = _read_config()
    return config["server"].rstrip("/"), config["token"]


def _version():
    """The version this copy was built as, for the Status message."""
    try:
        return str(_read_config().get("version") or "unknown")
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Pairing the open document with a draft link


def _matching_sessions(sessions, doc_name):
    """The user's draft links to a file of this name, in the server's order
    (newest first). More than one means the same file name is linked in
    several conversations, possibly on different matters."""
    return [s for s in sessions if s.get("name") == doc_name]


def _distinct_documents(matches):
    """One link per linked file, keeping the newest for each.

    Several conversations may link the same file. Those links share one
    connection on the server, so any of them will do and there is nothing
    to ask. Links to different files of the same name are different
    documents, and only the user knows which one is open. A server older
    than 0.4.0 does not say which file a link is to; its links are told
    apart by matter.
    """
    by_document = {}
    for session in matches:
        key = session.get("file") or ("matter", session.get("matter"))
        by_document.setdefault(key, session)
    return list(by_document.values())


def _session_label(session):
    """One line naming a link's matter and conversation, for the chooser and
    the confirmation. A server older than 0.4.0 sends no conversation."""
    matter = (session.get("matter") or "").strip() or "No matter"
    conversation = (session.get("conversation") or "").strip()
    if conversation:
        return f"{matter}: {conversation}"
    return matter


class Api:
    """Thin JSON client for the Kosmos companion endpoints."""

    def __init__(self, server, token):
        self.base = server + "/case/drafts/companion/api"
        self.token = token

    def _call(self, method, path, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={
                "X-Kosmos-Token": self.token,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))

    def sessions(self):
        return self._call("GET", "/sessions/")["sessions"]

    def hello(self, session_id, odt_b64):
        return self._call("POST", f"/{session_id}/hello/", {"odt_b64": odt_b64})

    def ops(self, session_id):
        return self._call("GET", f"/{session_id}/ops/")

    def result(self, session_id, round_id, payload):
        return self._call("POST", f"/{session_id}/rounds/{round_id}/", payload)

    def claim(self, session_id, round_id):
        """Ask whether the chat is still waiting on this round."""
        return self._call("POST", f"/{session_id}/rounds/{round_id}/", {"claim": True})


# ---------------------------------------------------------------------------
# Edit application (ported from the server's uno_driver, same semantics)


def _apply_replace(doc, edit, index):
    old, new = edit["old"], edit["new"]
    occurrence = edit.get("occurrence")

    finder = doc.createSearchDescriptor()
    finder.SearchString = old
    finder.setPropertyValue("SearchCaseSensitive", True)
    finder.setPropertyValue("SearchRegularExpression", False)
    found = doc.findAll(finder)
    matches = found.Count
    if matches == 0:
        raise CompanionError(f"text not found in the document: {old[:120]!r}", index)

    if occurrence:
        if occurrence > matches:
            raise CompanionError(
                f"occurrence {occurrence} of {old[:120]!r} requested but only "
                f"{matches} found",
                index,
            )
        target = found.getByIndex(occurrence - 1)
        cursor = target.getText().createTextCursorByRange(target)
        target.getText().insertString(cursor, new, True)
        return 1

    if matches > 1 and not edit.get("replace_all"):
        raise CompanionError(
            f"ambiguous edit: {matches} occurrences of {old[:120]!r} "
            "(set occurrence to pick one, or replace_all to change every one)",
            index,
        )

    replacer = doc.createReplaceDescriptor()
    replacer.SearchString = old
    replacer.ReplaceString = new
    replacer.setPropertyValue("SearchCaseSensitive", True)
    replacer.setPropertyValue("SearchRegularExpression", False)
    replaced = doc.replaceAll(replacer)
    if replaced != matches:
        raise CompanionError(
            f"expected {matches} replacement(s), made {replaced}", index
        )
    return replaced


def _find_paragraph(doc, needle, index, occurrence=None):
    matches = []
    enum = doc.getText().createEnumeration()
    while enum.hasMoreElements():
        par = enum.nextElement()
        if par.supportsService("com.sun.star.text.Paragraph") and needle in (
            par.getString()
        ):
            matches.append(par)
    if not matches:
        raise CompanionError(f"no paragraph contains: {needle[:120]!r}", index)
    if occurrence:
        if occurrence > len(matches):
            raise CompanionError(
                f"occurrence {occurrence} requested but only {len(matches)} "
                f"paragraphs contain {needle[:120]!r}",
                index,
            )
        return matches[occurrence - 1]
    if len(matches) > 1:
        raise CompanionError(
            f"ambiguous: {len(matches)} paragraphs contain {needle[:120]!r} "
            "(quote more of the paragraph, or set occurrence to pick one)",
            index,
        )
    return matches[0]


def _apply_delete_paragraph(doc, edit, index):
    par = _find_paragraph(doc, edit["text"], index, edit.get("occurrence"))
    text = doc.getText()
    cursor = text.createTextCursorByRange(par.getStart())
    cursor.gotoEndOfParagraph(True)
    cursor.goRight(1, True)
    text.insertString(cursor, "", True)


def _apply_insert_after(doc, edit, index):
    from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK

    par = _find_paragraph(doc, edit["anchor"], index, edit.get("occurrence"))
    text = doc.getText()
    cursor = text.createTextCursorByRange(par.getEnd())
    for ptext in edit["paragraphs"]:
        text.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
        text.insertString(cursor, ptext, False)


def _apply_edits(doc, edits):
    results = []
    for index, edit in enumerate(edits):
        op = edit.get("op", "replace")
        if op == "replace":
            replaced = _apply_replace(doc, edit, index)
        elif op == "delete_paragraph":
            _apply_delete_paragraph(doc, edit, index)
            replaced = 1
        elif op == "insert_after":
            _apply_insert_after(doc, edit, index)
            replaced = 1
        else:
            raise CompanionError(f"unknown edit op: {op!r}", index)
        results.append({"op": op, "replacements": replaced})
    return results


def _set_profile_name(ctx, given, surname):
    """Set the LibreOffice user name (tracked changes are attributed to it)
    and return the previous values so the caller can restore them."""
    provider = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.configuration.ConfigurationProvider", ctx
    )
    access = provider.createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationUpdateAccess",
        (_prop("nodepath", "/org.openoffice.UserProfile/Data"),),
    )
    previous = (
        access.getPropertyValue("givenname"),
        access.getPropertyValue("sn"),
    )
    access.setPropertyValue("givenname", given)
    access.setPropertyValue("sn", surname)
    access.commitChanges()
    return previous


def _apply_round(ctx, doc, edits):
    """Apply one round atomically: record changes as Kosmos AI, and undo the
    whole round if any edit fails."""
    doc.setPropertyValue("RecordChanges", True)
    if not doc.getPropertyValue("RecordChanges"):
        raise CompanionError(
            "change recording could not be enabled (is the document's "
            "tracked-changes protection on?)"
        )
    previous_name = _set_profile_name(ctx, AI_AUTHOR, "")
    undo = doc.getUndoManager()
    undo.enterUndoContext("Kosmos AI edits")
    try:
        results = _apply_edits(doc, edits)
    except Exception:
        undo.leaveUndoContext()
        try:
            undo.undo()
        except Exception:
            pass
        raise
    else:
        undo.leaveUndoContext()
        return results
    finally:
        try:
            _set_profile_name(ctx, *previous_name)
        except Exception:
            pass


def _export_odt_b64(doc):
    """A writer8 snapshot of the live document, base64-encoded. storeToURL
    saves a copy; the document's path and modified state are untouched."""
    fd, path = tempfile.mkstemp(suffix=".odt", prefix="kosmos-companion-")
    os.close(fd)
    try:
        doc.storeToURL(
            uno.systemPathToFileUrl(path),
            (_prop("FilterName", "writer8"), _prop("Overwrite", True)),
        )
        with open(path, "rb") as handle:
            return base64.b64encode(handle.read()).decode("ascii")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Connection state and poll loop


class _Connection:
    def __init__(self, ctx, api, doc, session):
        self.ctx = ctx
        self.api = api
        self.doc = doc
        self.session = session  # {"id", "name", "matter"}
        self.stop = threading.Event()
        self.last_note = "connected"
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        cycles = 0
        while not self.stop.is_set():
            try:
                data = self.api.ops(self.session["id"])
                if data.get("status") != "drafting":
                    self.last_note = "the draft link is no longer active in Kosmos"
                    break
                round_ = data.get("round")
                if round_:
                    self._handle_round(round_)
                    cycles = 0
                else:
                    cycles += 1
                    if cycles >= PUSH_EVERY_CYCLES:
                        self.api.hello(self.session["id"], _export_odt_b64(self.doc))
                        cycles = 0
            except DisposedException:
                self.last_note = "document was closed"
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (404, 410):
                    # The draft was unlinked in Kosmos; nothing to poll for.
                    self.last_note = "draft was unlinked in Kosmos"
                    break
                self.last_note = f"retrying after server error: {exc}"
            except Exception as exc:
                # Network blip or server hiccup: note it and keep polling.
                self.last_note = f"retrying after error: {exc}"
            self.stop.wait(POLL_SECONDS)

    def _handle_round(self, round_):
        # A server that asks for a claim (0.4.0 and later) is asked whether
        # the chat is still waiting before the document is touched. It has
        # given up when the round sat too long; the user has then been told
        # the edits were not applied, so they must not be. If the claim
        # itself cannot be made (network error) the round is likewise left
        # alone: the error propagates to the poll loop.
        if round_.get("claim"):
            answer = self.api.claim(self.session["id"], round_["id"])
            if not answer.get("apply"):
                self.last_note = (
                    "skipped a set of edits that Kosmos had stopped waiting "
                    "for (ask again in the chat)"
                )
                return
        try:
            results = _apply_round(self.ctx, self.doc, round_["edits"])
            payload = {"ok": True, "results": results}
            self.last_note = f"applied {len(results)} edit(s)"
        except CompanionError as exc:
            payload = {"ok": False, "error": str(exc), "edit_index": exc.edit_index}
            self.last_note = f"round failed: {exc}"
        except DisposedException:
            raise
        except Exception as exc:
            traceback.print_exc()
            payload = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "edit_index": None,
            }
            self.last_note = f"round failed: {exc}"
        try:
            payload["odt_b64"] = _export_odt_b64(self.doc)
        except Exception:
            pass
        self.api.result(self.session["id"], round_["id"], payload)


_connection = None
_lock = threading.Lock()


class Companion(unohelper.Base, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx

    # -- UI helpers

    def _desktop(self):
        return self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx
        )

    def _message(self, text, title="Kosmos Companion"):
        desktop = self._desktop()
        frame = desktop.getCurrentFrame()
        window = frame.getContainerWindow() if frame else None
        if window is None:
            return
        box = window.getToolkit().createMessageBox(
            window,
            uno.Enum("com.sun.star.awt.MessageBoxType", "INFOBOX"),
            1,  # BUTTONS_OK
            title,
            text,
        )
        box.execute()

    def _choose_session(self, doc_name, sessions):
        """Ask which of several draft links this document belongs to.

        Returns the chosen index, or None when the user cancels. Built in
        code (a list box and two buttons) so the extension ships no dialog
        resource files.
        """
        smgr = self.ctx.ServiceManager
        model = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", self.ctx
        )
        model.Title = "Kosmos Companion"
        model.PositionX = 60
        model.PositionY = 60
        model.Width = 260
        model.Height = 140

        def add(kind, name, x, y, width, height, **props):
            control = model.createInstance(f"com.sun.star.awt.UnoControl{kind}Model")
            control.Name = name
            control.PositionX = x
            control.PositionY = y
            control.Width = width
            control.Height = height
            for key, value in props.items():
                setattr(control, key, value)
            model.insertByName(name, control)

        add(
            "FixedText",
            "prompt",
            8,
            6,
            244,
            26,
            MultiLine=True,
            Label=(
                f'More than one file named "{doc_name}" is linked in Kosmos. '
                "Choose the matter and conversation this document belongs to."
            ),
        )
        add(
            "ListBox",
            "links",
            8,
            36,
            244,
            74,
            StringItemList=tuple(_session_label(s) for s in sessions),
        )
        # PushButtonType: 1 closes the dialog as OK, 2 as Cancel.
        add("Button", "ok", 142, 118, 52, 14, Label="Connect", PushButtonType=1)
        add("Button", "cancel", 200, 118, 52, 14, Label="Cancel", PushButtonType=2)

        dialog = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", self.ctx
        )
        dialog.setModel(model)
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        frame = self._desktop().getCurrentFrame()
        dialog.createPeer(toolkit, frame.getContainerWindow() if frame else None)
        try:
            links = dialog.getControl("links")
            links.selectItemPos(0, True)
            if dialog.execute() != 1:
                return None
            index = links.getSelectedItemPos()
            return index if 0 <= index < len(sessions) else None
        finally:
            dialog.dispose()

    # -- Commands (dispatched from the Kosmos menu)

    def trigger(self, command):
        try:
            if command == "connect":
                self._connect()
            elif command == "disconnect":
                self._disconnect(quiet=False)
            elif command == "status":
                self._status()
        except Exception as exc:
            traceback.print_exc()
            self._message(f"Something went wrong: {exc}")

    def _connect(self):
        global _connection
        try:
            server, token = _load_config()
        except Exception:
            self._message(
                "No configuration found. Download the extension from Kosmos "
                "(in a matter's AI chat, open Link a Draft and follow the "
                "LibreOffice companion extension link) so it carries your "
                "server address and token, then install it again."
            )
            return

        doc = self._desktop().getCurrentComponent()
        if doc is None or not doc.supportsService("com.sun.star.text.TextDocument"):
            self._message("Open the draft document in Writer first.")
            return
        url = doc.getURL()
        if not url:
            self._message(
                "This document has never been saved. Save it as an ODT file "
                "in the matter's Drive folder, link it to a conversation in "
                "Kosmos (Link a Draft), then connect again."
            )
            return
        doc_name = os.path.basename(uno.fileUrlToSystemPath(url))

        api = Api(server, token)
        try:
            sessions = api.sessions()
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                self._message(
                    "The server rejected this extension's token. Download a "
                    "fresh copy from Kosmos and reinstall it."
                )
            else:
                self._message(f"The Kosmos server answered with an error: {exc}")
            return
        except Exception as exc:
            self._message(f"Could not reach the Kosmos server at {server}: {exc}")
            return

        matches = _matching_sessions(sessions, doc_name)
        if not matches:
            self._message(
                f'No draft link found for "{doc_name}". In the matter\'s AI '
                "chat in Kosmos, link this document to a conversation (the "
                "pen button beside the message box opens Link a Draft), then "
                "connect again. The file name here must be the same as the "
                "linked file's name."
            )
            return
        session = matches[0]
        documents = _distinct_documents(matches)
        if len(documents) > 1:
            # Different files share this name. Pairing with the wrong one
            # would send another matter's edits here.
            try:
                index = self._choose_session(doc_name, documents)
            except Exception:
                # The chooser could not be shown. Fall back to the newest
                # link, as before; the confirmation below names it.
                traceback.print_exc()
                index = 0
            if index is None:
                return
            session = documents[index]

        with _lock:
            if _connection is not None:
                self._disconnect(quiet=True)
            try:
                doc.setPropertyValue("ShowChanges", True)
            except Exception:
                pass
            api.hello(session["id"], _export_odt_b64(doc))
            _connection = _Connection(self.ctx, api, doc, session)
            _connection.thread.start()

        self._message(
            f'Connected to the draft link for "{session["name"]}" '
            f"({_session_label(session)}). Edits you approve in that Kosmos "
            "chat now appear here as tracked changes, and the AI reads this "
            "document as you have it (hand edits included). Keep the "
            "document open; save whenever you are satisfied."
        )

    def _disconnect(self, quiet=False):
        global _connection
        connection = _connection
        _connection = None
        if connection is not None:
            connection.stop.set()
        if not quiet:
            if connection is None:
                self._message("The companion is not connected.")
            else:
                self._message(
                    f'Disconnected from "{connection.session["name"]}". '
                    "While disconnected, edits the AI proposes are not "
                    "applied. The AI goes on reading the draft from the copy "
                    "in Google Drive."
                )

    def _status(self):
        connection = _connection
        version = f"Companion version {_version()}."
        if connection is None:
            self._message(
                "Not connected. Use Kosmos > Connect to drafting session. " + version
            )
        elif not connection.thread.is_alive():
            self._message(
                f'The connection to "{connection.session["name"]}" has '
                f"stopped ({connection.last_note}). Connect again to resume. " + version
            )
        else:
            self._message(
                f'Connected to "{connection.session["name"]}" '
                f"({_session_label(connection.session)}). "
                f"Last activity: {connection.last_note}. " + version
            )


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    Companion, "law.kosmos.Companion", ("com.sun.star.task.Job",)
)
