"""Fixture-only STARTTLS catcher. Accepts/rejects locally; never forwards mail."""
import asyncio
import ssl
from pathlib import Path

from aiosmtpd.controller import Controller


class Catcher:
    async def handle_DATA(self, server, session, envelope):
        root = Path('/proof/mail')
        root.mkdir(exist_ok=True)
        if (root / 'reject').exists():
            return '451 Fixture delivery retry'
        (root / (str(len(list(root.glob('*.eml')))) + '.eml')).write_bytes(envelope.original_content)
        return '250 Stored in local fixture mail catcher'


context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('/proof/mail.crt', '/proof/mail.key')
controller = Controller(Catcher(), hostname='0.0.0.0', port=1025, tls_context=context, require_starttls=True)
controller.start()
print('Local mail catcher ready on SMTP 1025 with STARTTLS', flush=True)
asyncio.run(asyncio.Event().wait())
