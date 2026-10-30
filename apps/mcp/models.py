"""The remote MCP server's OAuth 2.1 records: the clients that may ask for
access (Claude, registered on its first visit), the short-lived codes the
consent screen issues, and each user's connections with their tokens.

Tokens, codes and client secrets are stored as SHA-256 digests. They are
long random strings, so a digest is enough: a copy of the table cannot be
replayed, and a presented token is looked up by hashing it.
"""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

ACCESS_TOKEN_LIFETIME = timedelta(hours=1)
# A connection nobody has refreshed in this long is over. Claude refreshes
# whenever it is used, so only an abandoned connection reaches this.
REFRESH_TOKEN_LIFETIME = timedelta(days=90)
CODE_LIFETIME = timedelta(minutes=5)
# A refresh token is single-use, but two of Claude's workers may refresh
# at the same moment. The second use of a just-rotated token inside this
# window issues another token pair instead of treating it as theft.
REFRESH_REUSE_GRACE = timedelta(seconds=60)


def digest(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def new_secret(prefix):
    return prefix + secrets.token_urlsafe(32)


class McpClient(models.Model):
    """An OAuth client. Registered dynamically (RFC 7591) or described by a
    client ID metadata document, in which case ``client_id`` is the
    document's URL and the row is a cache of it. A client has no access of
    its own: every token is a user's, issued on the consent screen."""

    client_id = models.CharField(max_length=512, unique=True)
    name = models.CharField(max_length=255)
    client_uri = models.URLField(max_length=512, blank=True)
    redirect_uris = models.JSONField(default=list)
    # Blank for a public client (Claude is one); otherwise the digest of
    # the secret issued at registration.
    secret_hash = models.CharField(max_length=64, blank=True)
    is_metadata_document = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mcp_client"

    def __str__(self):
        return self.name or self.client_id

    @property
    def is_public(self):
        return not self.secret_hash

    def check_secret(self, secret):
        return bool(secret) and secrets.compare_digest(self.secret_hash, digest(secret))


class McpAuthorizationCode(models.Model):
    """One authorization code, from the consent screen to the token
    endpoint. Deleted when redeemed; a code presented twice is refused."""

    code_hash = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(McpClient, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    redirect_uri = models.CharField(max_length=2048)
    code_challenge = models.CharField(max_length=128)
    resource = models.CharField(max_length=2048, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "mcp_authorization_code"

    @classmethod
    def issue(cls, *, client, user, redirect_uri, code_challenge, resource):
        code = new_secret("kmc_")
        cls.objects.create(
            code_hash=digest(code),
            client=client,
            user=user,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            resource=resource,
            expires_at=timezone.now() + CODE_LIFETIME,
        )
        return code

    @classmethod
    def redeem(cls, code, client):
        """The code's row, removed so it cannot be used again; None when it
        is unknown, expired, or belongs to another client. An expired code
        is removed too."""
        row = (
            cls.objects.select_related("user")
            .filter(code_hash=digest(code), client=client)
            .first()
        )
        if row is None:
            return None
        row.delete()
        if row.expires_at < timezone.now():
            return None
        return row


class McpConnection(models.Model):
    """A user's standing authorization of a client: what Settings > Claude
    lists and what Disconnect removes. Its tokens are McpToken rows."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mcp_connections",
    )
    client = models.ForeignKey(McpClient, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mcp_connection"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.client} for {self.user}"

    def touch(self):
        """Record a use, at most once a minute so a busy conversation is
        not a write per tool call."""
        now = timezone.now()
        if self.last_used_at is None or now - self.last_used_at > timedelta(minutes=1):
            self.last_used_at = now
            self.save(update_fields=["last_used_at"])


class McpToken(models.Model):
    """One access token and the refresh token that replaces it. Refreshing
    marks this row's refresh token used and creates the next row; the
    access token stays good until it expires, so a request already in
    flight on the old token still succeeds."""

    connection = models.ForeignKey(
        McpConnection, on_delete=models.CASCADE, related_name="tokens"
    )
    access_hash = models.CharField(max_length=64, unique=True)
    access_expires_at = models.DateTimeField()
    refresh_hash = models.CharField(max_length=64, unique=True)
    refresh_expires_at = models.DateTimeField()
    refresh_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mcp_token"

    @classmethod
    def issue(cls, connection):
        """A new token pair for the connection. Returns the plaintext
        tokens and the access token's lifetime in seconds."""
        access = new_secret("kma_")
        refresh = new_secret("kmr_")
        now = timezone.now()
        cls.objects.create(
            connection=connection,
            access_hash=digest(access),
            access_expires_at=now + ACCESS_TOKEN_LIFETIME,
            refresh_hash=digest(refresh),
            refresh_expires_at=now + REFRESH_TOKEN_LIFETIME,
        )
        # Rows whose both tokens are spent say nothing any more.
        cls.objects.filter(
            connection=connection,
            access_expires_at__lt=now,
            refresh_used_at__lt=now - REFRESH_REUSE_GRACE,
        ).delete()
        return access, refresh, int(ACCESS_TOKEN_LIFETIME.total_seconds())

    @classmethod
    def by_access_token(cls, token):
        """The live connection the access token belongs to, or None."""
        if not token:
            return None
        row = (
            cls.objects.select_related("connection__user", "connection__client")
            .filter(access_hash=digest(token), access_expires_at__gt=timezone.now())
            .first()
        )
        if row is None or not row.connection.user.is_active:
            return None
        return row.connection

    @classmethod
    def refresh(cls, token, client):
        """Rotate: mark the refresh token used and issue a new pair on the
        same connection. None when the token is unknown, expired, or for
        another client. A token reused after the grace window is treated
        as stolen: the whole connection is revoked (OAuth 2.1 section
        4.3.1), and the user connects again from Claude."""
        if not token:
            return None
        row = (
            cls.objects.select_related("connection__user")
            .filter(refresh_hash=digest(token), connection__client=client)
            .first()
        )
        if row is None or not row.connection.user.is_active:
            return None
        now = timezone.now()
        if row.refresh_expires_at < now:
            return None
        if row.refresh_used_at is not None:
            if now - row.refresh_used_at > REFRESH_REUSE_GRACE:
                row.connection.delete()
                return None
        else:
            row.refresh_used_at = now
            row.save(update_fields=["refresh_used_at"])
        return row.connection
