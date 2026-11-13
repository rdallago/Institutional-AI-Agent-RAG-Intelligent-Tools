"""Lectura local de la skill empaquetada; sin rutas del cliente o del PDF."""
from pathlib import Path

from app.application.agent.skills.registry import Skill
from app.application.ia.exceptions import IANoDisponible


class PackagedSkillLoader:
    def load(self, name):
        if name not in ('academic-rag', 'weather'):
            raise IANoDisponible()
        try:
            path = Path(__file__).resolve().parents[2] / 'application' / 'agent' / 'skills' / name / 'SKILL.md'
            if path.is_symlink() or path.stat().st_size > 12000:
                raise ValueError()
            content = path.read_text(encoding='utf-8')
            start, end = '<!-- runtime -->', '<!-- /runtime -->'
            if content.count(start) != 1 or content.count(end) != 1:
                raise ValueError()
            return Skill(name, content.split(start)[1].split(end)[0].strip())
        except Exception:
            raise IANoDisponible() from None
