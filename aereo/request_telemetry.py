"""Minimal per-request telemetry for GeoInsight.

- Generates server-side IDs; never trusts client-supplied request IDs.
- Logs route templates, not raw paths, query strings, client IPs or payloads.
- Exposes elapsed *to response start* via Server-Timing, and logs full ASGI call duration.
- Adds no external dependencies, background tasks, or database tables.
"""
from __future__ import annotations

import json
import logging
import time
from uuid import uuid4

from starlette.datastructures import MutableHeaders

LOG = logging.getLogger('uvicorn.error')


class RequestTelemetryMiddleware:
    """Pure ASGI middleware, independent of the request handler and DB sessions."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        request_id = uuid4().hex
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_telemetry(message):
            nonlocal status, response_started
            if message['type'] == 'http.response.start':
                status = int(message['status'])
                response_started = True
                headers = MutableHeaders(scope=message)
                # Fresh server-generated ID, even if the caller supplied X-Request-ID.
                headers['X-Request-ID'] = request_id
                # This measures the time to the response's initial headers, not
                # body transmission (the structured log covers the full ASGI call).
                headers['Server-Timing'] = (
                    f'app;dur={(time.perf_counter() - started) * 1000:.2f}'
                )
            await send(message)

        try:
            await self.app(scope, receive, send_with_telemetry)
        finally:
            # FastAPI supplies the matched route template, which avoids logging
            # resource IDs, raw file names, query parameters or unknown paths.
            route = scope.get('route')
            route_template = getattr(route, 'path', '[unmatched]')
            event = {
                'event': 'http_request',
                'request_id': request_id,
                'method': scope.get('method', 'UNKNOWN'),
                'route': route_template,
                'status_code': status if response_started else 500,
                'duration_ms': round((time.perf_counter() - started) * 1000, 2),
            }
            level = logging.WARNING if event['status_code'] >= 500 or event['duration_ms'] >= 1000 else logging.INFO
            LOG.log(level, json.dumps(event, separators=(',', ':'), ensure_ascii=True))
