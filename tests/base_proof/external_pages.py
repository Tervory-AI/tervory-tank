"""Offline HTTP boundary for real Tank proof; no application routes are replaced."""
import httpx

HTML = """<!doctype html><html><head><title>Fixture Shop</title></head><body>
<h1>Fixture Shop</h1><p>Fixture Shop, 1 Fixture Road, Austin, TX 78701.
Our independent store supplies business equipment and repairs. Call +1 512 555 0101.</p>
<a href="/contact">Contact our team</a><a href="mailto:info@shop.example">Email</a>
<a href="https://www.facebook.com/fixture-shop">Facebook</a>
<a href="https://www.tiktok.com/@fixture-shop">TikTok</a>
<p>Visit our store for product advice, service and support. Our team works with local businesses.</p>
</body></html>"""


def response(request: httpx.Request) -> httpx.Response:
    if request.url.host == "shop.example":
        return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})
    if request.url.host == "cloudflare-dns.com":
        return httpx.Response(200, json={"Status": 0, "Answer": [{"type": 15, "data": "10 mail.shop.example."}]})
    # All other external services are unavailable; proof cannot spend money or read live sites.
    return httpx.Response(503, json={"error": "External service unavailable in local fixture proof"})


def install() -> None:
    original = httpx.AsyncClient._transport_for_url
    fixture = httpx.MockTransport(response)

    def transport(self, url):
        if url.host in {"127.0.0.1", "localhost", "::1"}:
            return original(self, url)
        return fixture

    httpx.AsyncClient._transport_for_url = transport
