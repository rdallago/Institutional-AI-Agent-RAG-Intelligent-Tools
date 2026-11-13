"""Planes y argumentos cerrados. Ninguna salida del modelo es codigo."""
import json
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.ia.exceptions import IARespuestaInvalida


class WeatherArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    ciudad: str = Field(min_length=2, max_length=80)
    pais: str = Field(pattern=r'^[A-Z]{2}$')
    region: str = Field(default='', max_length=80)
    dia: Literal['hoy', 'mañana', 'pasado mañana', 'fecha'] = 'hoy'
    fecha: str | None = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')

    @field_validator('fecha')
    @classmethod
    def valid_date(cls, value):
        if value is not None: date.fromisoformat(value)
        return value

    @model_validator(mode='after')
    def date_mode(self):
        if (self.dia == 'fecha') != (self.fecha is not None):
            raise ValueError('Fecha y modo incompatibles')
        return self

    @field_validator('ciudad', 'region')
    @classmethod
    def location(cls, value):
        if any(not (c.isalpha() or c in " '-") for c in value):
            raise ValueError('Ubicacion invalida.')
        return value.strip()


class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    capacidad: Literal['academic-rag', 'weather', 'llm-directo', 'clarify']
    argumentos: dict = Field(default_factory=dict)


class ToolRegistry:
    names = frozenset({'academic-rag', 'weather', 'llm-directo', 'clarify'})

    def validate_proposal(self, raw):
        from .planning import validate_proposal
        return validate_proposal(raw)

    def validate(self, raw):
        try:
            def pairs(items):
                result = {}
                for k,v in items:
                    if k in result: raise ValueError()
                    result[k] = v
                return result
            plan = Plan.model_validate(json.loads(raw, object_pairs_hook=pairs))
            if plan.capacidad == 'weather':
                WeatherArgs.model_validate(plan.argumentos)
            elif plan.argumentos:
                raise ValueError()
            return plan
        except Exception:
            raise IARespuestaInvalida() from None


COUNTRIES = {'argentina':'AR', 'uruguay':'UY', 'chile':'CL', 'brasil':'BR',
             'espana':'ES', 'mexico':'MX', 'paraguay':'PY', 'bolivia':'BO',
             'peru':'PE', 'colombia':'CO', 'estados unidos':'US'}

MONTHS = dict(zip(('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(), range(1,13)))
DATE_PATTERN = (r'\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})|'
                r'\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{4})\b')


def weather_date(question):
    """Extrae intención temporal; las fechas relativas se resuelven en la ubicación."""
    from .router import normalize
    text = normalize(question)
    found = re.findall(DATE_PATTERN, text)
    relative = re.findall(r'\b(?:pasado manana|manana|hoy)\b', text)
    if len(found) + len(relative) > 1: raise ValueError('Fecha ambigua')
    if found:
        value = found[0]
        if '/' in value:
            day,month,year = map(int,value.split('/'))
            # Política explícita: años abreviados 00–99 representan 2000–2099.
            if len(value.split('/')[-1]) == 2: year += 2000
        elif ' de ' in value:
            day,month,year = value.split(' de ')
            day,month,year = int(day),MONTHS.get(month,0),int(year)
        else:
            year,month,day = map(int,value.split('-'))
        return 'fecha', date(year,month,day).isoformat()
    return ({'manana':'mañana','pasado manana':'pasado mañana','hoy':'hoy'}.get(relative[0],'hoy') if relative else 'hoy'), None


def weather_arguments(question, previous=None):
    from .router import normalize
    day, explicit = weather_date(question)
    # Separar el sufijo temporal ANTES de interpretar el país.
    match = re.search(r'\ben\s+(.+?)[?¿!.]*$', question, re.IGNORECASE)
    if match:
        location = re.split(r'\s+(?:(?:el\s+)?d[ií]a\s+|el\s+(?=\d)|(?=(?:pasado\s+ma[ñn]ana|ma[ñn]ana|hoy)\b)|(?=\d{1,4}[/\-]))', match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
        parts = [p.strip(' ?¿!.') for p in location.split(',')]
        if parts:
            parts[0] = re.sub(r'^(?:(?:la|el)\s+)?(?:ciudad|localidad|municipio)\s+de\s+',
                              '', parts[0], flags=re.IGNORECASE).strip()
        if len(parts) in (2,3):
            country = COUNTRIES.get(normalize(parts[-1]), parts[-1].upper())
            try:
                return WeatherArgs(ciudad=parts[0], pais=country,
                    region=parts[1] if len(parts)==3 else '', dia=day, fecha=explicit)
            except ValueError:
                return None
    if previous and not match:
        try:
            return WeatherArgs.model_validate({**previous, 'dia':day, 'fecha':explicit})
        except ValueError:
            return None
    return None
