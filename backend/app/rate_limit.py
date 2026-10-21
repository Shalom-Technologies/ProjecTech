from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_key(request: Request) -> str:
    """
    Who is making this request, for rate limiting.

    On Fly.io every request arrives through Fly's proxy, so the plain connection address is
    the proxy and all users would share one limit. Fly puts the real visitor address in the
    Fly-Client-IP header and overwrites any value a visitor sends, so it cannot be faked.
    X-Forwarded-For is NOT used: with the server configured to trust it, a visitor can send
    a made-up value and get a fresh limit on every request.
    """
    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip:
        return fly_ip.strip()
    return get_remote_address(request)  # local development


limiter = Limiter(key_func=client_key)
