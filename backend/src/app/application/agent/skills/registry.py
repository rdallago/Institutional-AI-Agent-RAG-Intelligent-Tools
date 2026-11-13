from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from app.application.ia.exceptions import IANoDisponible


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    instructions: str = field(repr=False)

    async def execute(self, service, principal, document_id, question):
        # La skill aporta instrucciones acotadas; NO sustituye ACL/citas/cuotas.
        return await service.execute(principal, document_id, question,
                                     instructions=self.instructions)


class SkillLoader(Protocol):
    def load(self, name: str) -> Skill: ...


class SkillRegistry:
    """Allowlist fija. No admite rutas, Markdown ni nombres del cliente/PDF."""
    def __init__(self, loader: SkillLoader):
        self.loader = loader

    @lru_cache(maxsize=1)
    def load(self, name):
        if name not in ('academic-rag', 'weather'):
            raise IANoDisponible()
        try:
            skill = self.loader.load(name)
            if not isinstance(skill, Skill) or skill.name != name:
                raise ValueError()
            instructions = skill.instructions
            if not instructions or len(instructions.encode('utf-8')) > 512 or '\x00' in instructions:
                raise ValueError()
            return skill
        except Exception:
            raise IANoDisponible() from None
