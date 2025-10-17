"""Local HTTPS callback server to capture OAuth authorization code."""

import asyncio
import ssl
from typing import Dict, Any, Tuple
from aiohttp import web


async def _handle_callback(request: web.Request) -> web.Response:
    request.app['auth_result'] = {
        'code': request.query.get('code'),
        'state': request.query.get('state'),
        'error': request.query.get('error'),
        'error_description': request.query.get('error_description'),
    }
    return web.Response(text="You can close this window and return to the app.")


async def _handle_root(_: web.Request) -> web.Response:
    # Friendly page to avoid 404 confusion when users navigate to '/'
    html = (
        "<html><head><title>OAuth Callback Server</title></head><body>"
        "<h2>OAuth Callback Server Running</h2>"
        "<p>This local server only handles the <code>/callback</code> path used by the OAuth redirect.</p>"
        "<p>If you see this page, the OAuth provider hasn't redirected back yet. Please continue the sign-in flow in your browser.</p>"
        "</body></html>"
    )
    return web.Response(text=html, content_type='text/html')


async def _handle_favicon(_: web.Request) -> web.Response:
    return web.Response(status=204)


async def run_https_callback_server(host: str, port: int, cert_path: str, key_path: str, timeout: int = 120) -> Dict[str, Any]:
    """Run a temporary HTTPS server to receive /callback.

    Returns a dict with code/state or error.
    """
    app = web.Application()
    app.add_routes([
        web.get('/', _handle_root),
        web.get('/favicon.ico', _handle_favicon),
        web.get('/callback', _handle_callback),
    ])
    app['auth_result'] = None

    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port, ssl_context=ssl_ctx)
    await site.start()

    try:
        # Wait until auth_result is set or timeout
        for _ in range(timeout):
            await asyncio.sleep(1)
            if app['auth_result'] is not None:
                return app['auth_result']
        return {'error': 'timeout', 'error_description': 'No callback received'}
    finally:
        await runner.cleanup()
