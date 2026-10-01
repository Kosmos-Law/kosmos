from django.test import RequestFactory

from utils.ratelimit import client_ip


def test_client_ip_is_the_address_the_proxy_appended():
    """nginx appends the peer address to whatever X-Forwarded-For the client
    sent. Only that last entry can be trusted; the first is the caller's to
    choose."""
    request = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7", REMOTE_ADDR="127.0.0.1"
    )

    assert client_ip(request) == "198.51.100.7"


def test_client_ip_cannot_be_rotated_by_a_forged_header():
    factory = RequestFactory()
    seen = {
        client_ip(factory.get("/", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}, 198.51.100.7"))
        for i in range(5)
    }

    assert seen == {"198.51.100.7"}


def test_client_ip_without_a_proxy_is_the_peer_address():
    request = RequestFactory().get("/", REMOTE_ADDR="203.0.113.9")

    assert client_ip(request) == "203.0.113.9"
