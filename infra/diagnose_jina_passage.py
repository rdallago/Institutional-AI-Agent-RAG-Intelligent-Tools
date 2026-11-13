"""Prueba optativa, exclusivamente sintética. Sin red salvo --execute."""
import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend' / 'src'))
from app.infrastructure.configuration.embeddings import EmbeddingConfig
from app.infrastructure.rag.jina import JinaEmbeddings
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado, IARespuestaInvalida, PromptInvalido

SYNTHETIC = 'El Instituto de Prueba tiene una biblioteca con veinte libros de programación.'


def failure(error, stage, status=None):
    """Solo categorías conocidas; jamás interpolar str/repr del error upstream."""
    if isinstance(error, KeyboardInterrupt):
        code, description = 'interrupted', 'Interrumpido; el resultado remoto puede ser incierto. No reintentar automáticamente.'
    elif stage == 'configuration':
        code, description = 'invalid_configuration', 'Configuración rechazada; comprobar formato de clave y parámetros admitidos.'
    elif stage == 'resources':
        code, description = 'resource_check_failed', 'No se confirmó la reserva de RAM de 0,25 GiB; sin solicitud HTTP.'
    elif stage == 'client_initialization':
        code, description = 'client_initialization_failed', 'No se pudo construir el cliente: revisar clave, transporte y entorno SSL. Sin solicitud HTTP.'
    elif stage == 'client_close':
        code, description = 'client_close_failed', 'Falló el cierre de recursos; no repetir una solicitud que pudo completarse.'
    elif status in (401, 402, 403, 429):
        code, description = {
            401: ('authentication_rejected', 'El proveedor rechazó la autenticación.'),
            402: ('payment_or_balance_rejected', 'El proveedor rechazó la solicitud por pago o saldo.'),
            403: ('access_or_balance_rejected', 'El proveedor denegó acceso; puede incluir saldo insuficiente. Causa exacta no conservada.'),
            429: ('rate_limited', 'El proveedor limitó la solicitud; sin reintentos.'),
        }[status]
    elif isinstance(error, IATiempoAgotado):
        code, description = 'timeout', 'Se agotó el plazo; el resultado remoto puede ser incierto.'
    elif status is not None and status >= 500:
        code, description = 'provider_unavailable', 'El proveedor devolvió un error de servicio.'
    elif isinstance(error, IANoDisponible):
        code, description = 'availability_or_transport_failed', 'Fallo de disponibilidad, recursos o transporte; sin causa interna diferenciada.'
    elif isinstance(error, IARespuestaInvalida):
        code, description = 'invalid_response', 'Contrato HTTP/JSON, modelo, índice, cantidad, dimensión, valores o norma rechazados.'
    elif isinstance(error, PromptInvalido):
        code, description = 'invalid_input', 'La validación local rechazó la entrada.'
    else:
        code, description = 'local_error', 'Fallo local no clasificado; no se muestran detalles de excepción.'
    allowed = (ValueError, TypeError, RuntimeError, OSError, IANoDisponible,
               IATiempoAgotado, IARespuestaInvalida, PromptInvalido, KeyboardInterrupt)
    error_type = next((kind.__name__ for kind in allowed if isinstance(error, kind)), 'Exception')
    return {'stage': stage, 'error_type': error_type, 'error_code': code, 'description': description}


async def probe(config, *, transport=None):
    """No admite texto, archivo o URL de entrada. Nunca habilita embed_document."""
    provider = None
    status = None
    async def observe(response):
        nonlocal status
        status = response.status_code
    result = {'model': config.model, 'task': 'retrieval.passage', 'synthetic_only': True,
              'valid': False}
    start = monotonic()
    stage = 'resources'
    try:
        if not config.testing:
            from app.infrastructure.rag.resources import require_memory
            require_memory(.25)  # La guarda del adaptador también sigue activa.
        stage = 'client_initialization'
        provider = JinaEmbeddings(config, transport=transport)
        provider.client.event_hooks['response'].append(observe)
        stage = 'request_and_validation'
        # Transporte/validación compartidos; el único texto está fijado arriba.
        # No cambiar DOCUMENT_EXPORT_APPROVED ni invocar el reindexador.
        vector = await provider._embed(SYNTHETIC, 'retrieval.passage', config.space)
        result.update(valid=True, dimensions=len(vector), finite=all(math.isfinite(v) for v in vector),
                      norm=round(math.hypot(*vector), 6))
    except Exception as error:
        result.update(failure(error, stage, status))
    finally:
        result.update(http=status, duration_seconds=round(monotonic()-start, 3))
        if provider is not None:
            try:
                await provider.close()
            except Exception as error:
                cleanup = failure(error, 'client_close', status)
                if 'error_code' in result:
                    result['cleanup_error'] = cleanup  # Conservar el fallo original.
                else:
                    result.update(cleanup)
                result['valid'] = False
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Una solicitud sintética; requiere autorización adicional.')
    args = parser.parse_args(argv)
    if not args.execute:
        print('SIN SOLICITUDES: prueba preparada; requiere autorización adicional y --execute.')
        return 0
    stage = 'configuration'
    try:
        key = os.environ.get('JINA_API_KEY', '')
        if not key.strip():
            print(json.dumps({'valid': False, 'http': None, 'stage': stage,
                'error_type': 'ValueError', 'error_code': 'missing_api_key',
                'description': 'JINA_API_KEY no está disponible en este proceso Python. Configurar $env:JINA_API_KEY en la misma terminal.'}, ensure_ascii=True, indent=2))
            return 2
        config = EmbeddingConfig(provider='jina', api_key=key)
        stage = 'execution'
        result = asyncio.run(probe(config))
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({'valid': False, **failure(error, stage)}, ensure_ascii=True, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
