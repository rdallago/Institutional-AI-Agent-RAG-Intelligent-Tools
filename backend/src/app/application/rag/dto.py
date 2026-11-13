from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class Section:
    start: int
    end: int
    title: str = field(repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class Page:
    number: int
    text: str = field(repr=False)
    sections: tuple[Section, ...] = field(default=(), repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class Scope:
    document_id: UUID
    version_id: UUID
    # Identidad inmutable del modelo/digest y politica de embeddings; no solo dimension.
    space: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleLink:
    number: int
    group: str
    section: str
    first_page: int
    closure: str
    scope: Scope


@dataclass(frozen=True, slots=True, kw_only=True)
class RequirementList:
    scope: Scope
    page: int
    start: int
    end: int
    sha256: str
    item_spans: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Chunk:
    id: str
    scope: Scope
    page: int
    start: int
    end: int
    text: str = field(repr=False)
    section: str = field(repr=False)
    article: ArticleLink | None = field(default=None, repr=False)
    requirements: RequirementList | None = field(default=None, repr=False)
    ordinal: int | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidate:
    chunk: Chunk = field(repr=False)
    similarity: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    citation: str
    chunk: Chunk = field(repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class GroundedInput:
    question: str = field(repr=False)
    evidence: tuple[Evidence, ...] = field(repr=False)
    rendered: str = field(repr=False)
    instructions: str = field(default='', repr=False)
    context_tokens: int = field(default=4096, init=False)
    max_output_tokens: int = field(default=256, init=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class RAGResult:
    status: str
    answer: str = field(repr=False)
    citations: tuple[Evidence, ...] = field(default=(), repr=False)
    finalization: str | None = None
    strategy: str = field(default='RAG', init=False)
