"""Limite real de cuerpo antes del parser de FastAPI; sin acumular cuerpos ilimitados."""
from app.presentation.http.errors import error_response


class IABodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope.get('path','').startswith('/api/v1/ia/'):
            return await self.app(scope, receive, send)

        async def no_store(message):
            if message['type'] == 'http.response.start':
                message = {**message, 'headers': [(k,v) for k,v in message.get('headers',[])
                    if k.lower() != b'cache-control'] + [(b'cache-control',b'no-store')]}
            await send(message)

        if scope.get('method') != 'POST':
            return await self.app(scope, receive, no_store)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body',b'')
            if len(body) + len(chunk) > 16384:
                response = error_response(413,'SOLICITUD_DEMASIADO_GRANDE','El cuerpo supera el limite admitido.')
                return await response(scope, receive, no_store)
            body.extend(chunk)
            if not message.get('more_body',False):
                break
        content_types = [v.decode('latin-1') for k,v in scope.get('headers',[]) if k.lower()==b'content-type']
        media = content_types[0].split(';')[0].strip().lower() if len(content_types)==1 else ''
        if media != 'application/json':
            response = error_response(422,'SOLICITUD_INVALIDA','Se requiere contenido application/json.')
            return await response(scope, receive, no_store)
        try:
            body.decode('utf-8')
        except UnicodeError:
            response = error_response(422,'SOLICITUD_INVALIDA','Se requiere JSON con codificacion UTF-8 valida.')
            return await response(scope, receive, no_store)
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        await self.app(scope, replay, no_store)
