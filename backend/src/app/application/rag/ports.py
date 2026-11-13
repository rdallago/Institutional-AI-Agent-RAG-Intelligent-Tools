from typing import Protocol
from uuid import UUID

from app.application.auth.service import Principal
from app.application.ia.dto import GeneracionSalida
from app.application.rag.dto import Candidate, Chunk, GroundedInput, Scope
from app.application.rag.structured_output import StructuredGeneration


class TokenCounter(Protocol):
    """Tokenizador versionado compatible; contar el render completo, no caracteres."""
    identity: str
    def count(self, text: str) -> int: ...


class EmbeddingProvider(Protocol):
    """Consulta/documento comparten identidad de espacio; nunca mezclar modelos."""
    async def embed_query(self, text: str, *, space: str) -> tuple[float, ...]: ...

    async def embed_document(self, text: str, *, space: str) -> tuple[float, ...]:
        """Un fragmento por llamada futura; prefijo search_document, sin publicacion."""
        ...


class GroundedLLMProvider(Protocol):
    """Debe enviar rendered sin alterar plantilla, con qwen3:1.7b/think=false.

    No acepta opciones del usuario. El adaptador futuro debe comprobar tambien
    su plantilla/tokenizacion y preservar el parser estricto stop/length.
    """
    async def generate_grounded(self, input: GroundedInput) -> GeneracionSalida | StructuredGeneration: ...


class DocumentRepository(Protocol):
    async def article_context(self, principal: Principal, scope: Scope,
                              seeds: tuple[Chunk, ...]) -> tuple[Chunk, ...]:
        """Slices contiguos exactos de articulos completos, ACL/version revalidadas.

        Ventana acotada; vacio si no se prueba continuidad/fin. Sin escrituras.
        """
        ...

    async def require_active(self, principal: Principal, document_id: UUID) -> Scope:
        """ACL normal + version LISTA activa, sin acceso implicito por ADMIN."""
        ...

    async def put_prepared_once(self, principal: Principal, scope: Scope,
                                key: str, chunks: tuple[Chunk, ...]) -> str:
        """Atomicamente revalida ACL de ingesta y deduplica por documento/version/key.

        Solo staging; nunca publicar una version sin embeddings/revision.
        Devuelve la misma key o falla; no mantener transaccion durante modelos.
        """
        ...


class VectorRepository(Protocol):
    async def put_once(self, principal: Principal, scope: Scope, chunk: Chunk,
                       vector: tuple[float, ...]) -> None:
        """Checkpoint atomico autorizado de staging por version/chunk/space.

        No sobreescribir silenciosamente vectores diferentes para la misma clave.
        """
        ...

    async def search(self, principal: Principal, scope: Scope,
                     vector: tuple[float, ...], *, limit: int) -> tuple[Candidate, ...]:
        """Filtrar ACL, version LISTA activa y espacio ANTES de top-k coseno.

        Sin resultados es (); indice ausente/fallo NO es una lista vacia.
        """
        ...


class WorkLease(Protocol):
    def release(self) -> None: ...


class ModelWorkGate(Protocol):
    def try_acquire(self) -> WorkLease: ...
