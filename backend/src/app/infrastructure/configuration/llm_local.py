"""Prueba de enlace local requerida antes de habilitar IA operativa; no arranca servicios."""
from dataclasses import dataclass, field
import os
import socket

from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalLLMContext:
    listener: socket.socket = field(repr=False)
    workers: int


def require_local_runtime(config: LLMConfig, context: LocalLLMContext | None) -> None:
    if not config.enabled or config.testing:
        return
    try:
        valid = (config.environment == 'local-development' and isinstance(context,LocalLLMContext)
            and type(context.workers) is int and context.workers==1
            and os.environ.get('WEB_CONCURRENCY','1')=='1'
            and context.listener.family==socket.AF_INET
            and context.listener.getsockname()[0]=='127.0.0.1'
            and context.listener.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1)
    except (OSError,AttributeError):
        valid = False
    if not valid:
        raise LLMConfigInvalida()
