"""Whether this server can start a Google sign-in at all.

Every Google integration (Contacts, Calendar, Drive and each user's Gmail)
connects through one OAuth client, whose secret file an administrator saves
as ``google_tokens.json`` in ``GOOGLE_DATA_DIR``. Until that file exists and
holds a client, a Connect button can only fail, so the pages that offer one
ask here first.
"""

import json

from django.conf import settings


def google_oauth_configured():
    """True when the OAuth client secret file exists and holds a client.

    Google's client files carry one top-level key, ``web`` or
    ``installed``, holding the client id; anything else (a missing file,
    an empty one, a token file saved under the wrong name) cannot start a
    sign-in.
    """
    try:
        with open(settings.GOOGLE_CLIENT_SECRET_PATH, "r") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    client = data.get("web") or data.get("installed")
    return isinstance(client, dict) and bool(client.get("client_id"))
