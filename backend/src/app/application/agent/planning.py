"""Propuestas semánticas acotadas; nunca ejecutan código ni conceden permisos."""
import json
from typing import Annotated, Literal
from pydantic import ValidationError

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from app.application.ia.exceptions import IARespuestaInvalida
from .tools import WeatherArgs


class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class WeatherArguments(Arguments):
    ciudad: str | None = Field(max_length=80)
    provincia: str | None = Field(max_length=80)
    pais: str | None = Field(max_length=100)
    fecha: str | None = Field(max_length=16)

    @field_validator('ciudad', 'provincia')
    @classmethod
    def location(cls, value):
        return WeatherArgs.location(value) if value is not None else None

    @field_validator('fecha')
    @classmethod
    def temporal(cls, value):
        if value is not None and value not in ('hoy', 'mañana', 'pasado mañana'):
            from datetime import date
            if len(value)!=10: raise ValueError('Fecha ISO requerida')
            date.fromisoformat(value)
        return value

    def resolved(self):
        if not self.ciudad or not self.pais or self.fecha is None: return None
        relative = self.fecha in ('hoy','mañana','pasado mañana')
        return WeatherArgs(ciudad=self.ciudad, region=self.provincia or '', pais=self.pais,
                           dia=self.fecha if relative else 'fecha', fecha=None if relative else self.fecha)


class DocumentArguments(Arguments):
    documento_id: str | None = Field(max_length=36)
    documento_solicitado: str | None = Field(max_length=200)
    consulta: str = Field(min_length=1, max_length=1000)

    @field_validator('consulta')
    @classmethod
    def bounded_query(cls,value):
        from app.application.ia.dto import ConsultaDatos, validate_prompt
        validate_prompt(ConsultaDatos(prompt=value))
        return value

    @field_validator('documento_id')
    @classmethod
    def identifier(cls, value):
        from uuid import UUID
        if value is not None: UUID(value)
        return value


class EmptyArguments(Arguments):
    pass


class ClarificationArguments(Arguments):
    motivo: Literal['ubicacion', 'fecha', 'documento', 'intencion']


class WeatherProposal(Arguments):
    accion: Literal['consultar_clima']
    argumentos: WeatherArguments


class DocumentProposal(Arguments):
    accion: Literal['consultar_documentos_academicos']
    argumentos: DocumentArguments


class DirectProposal(Arguments):
    accion: Literal['responder_llm_directo']
    argumentos: EmptyArguments


class ClarificationProposal(Arguments):
    accion: Literal['solicitar_aclaracion']
    argumentos: ClarificationArguments


Proposal = TypeAdapter(Annotated[WeatherProposal | DocumentProposal | DirectProposal | ClarificationProposal,
                                  Field(discriminator='accion')])


def validate_proposal(raw):
    from .diagnostics import record_private
    proposal_type = 'unknown'
    class DuplicateKey(ValueError):
        pass
    try:
        def pairs(items):
            result={}
            for key,value in items:
                if key in result:raise DuplicateKey()
                result[key]=value
            return result
        data = json.loads(raw, object_pairs_hook=pairs)
        action = data.get('accion') if type(data) is dict else None
        if action in {'consultar_clima','consultar_documentos_academicos','responder_llm_directo','solicitar_aclaracion'}:
            proposal_type = action
        result = Proposal.validate_python(data)
        record_private('planner_validation', proposal_type=proposal_type, reason='valid')
        return result
    except ValidationError as error:
        fields = {'accion','argumentos','ciudad','provincia','pais','fecha','documento_id','documento_solicitado','consulta','motivo'}
        rules = [{'field':'.'.join(str(x) if x in fields else '[redacted]' for x in item['loc']),
                  'rule':item['type']} for item in error.errors(include_input=False,include_context=False,include_url=False)[:8]]
        record_private('planner_validation', proposal_type=proposal_type, reason='schema_rejected', rules=rules)
        raise IARespuestaInvalida() from None
    except (json.JSONDecodeError, DuplicateKey) as error:
        record_private('planner_validation', proposal_type=proposal_type,
                       reason='duplicate_key' if isinstance(error, DuplicateKey) else 'json_syntax')
        raise IARespuestaInvalida() from None
    except Exception:
        record_private('planner_validation', proposal_type=proposal_type, reason='invalid_structure')
        raise IARespuestaInvalida() from None


def planning_context(question, history, catalog, selected):
    """Datos no confiables, sin Principal/JWT ni respuestas documentales recicladas."""
    from .context import contextual_reference
    data={'pregunta_actual':question,'documento_seleccionado':str(selected) if selected else None,
          'ubicacion_previa':None,'historial_no_confiable':[], 'documentos_autorizados':[]}
    # Solo metadatos meteorológicos validados; no imponerlos a la intención actual.
    for message in reversed(history):
        if message.get('role')=='assistant' and message.get('tool')=='consultar_clima':
            try:data['ubicacion_previa']=WeatherArgs.model_validate(message.get('tool_context',{})).model_dump()
            except ValueError:pass
            break
    def fits(): return len(json.dumps(data,ensure_ascii=False).encode('utf-8'))<=2400
    for row in catalog[:8]:
        item={'id':str(row['id']),'titulo':row['titulo']}
        data['documentos_autorizados'].append(item)
        if not fits():data['documentos_autorizados'].pop();break
    for message in reversed(history[-8:] if contextual_reference(question) else ()):
        if message['role']!='user':continue
        data['historial_no_confiable'].insert(0,message['content'][:160])
        if not fits():data['historial_no_confiable'].pop(0);break
    return json.dumps(data,ensure_ascii=False,separators=(',',':'))


def matches_document(requested, title):
    """Filtro conservador de identidad, no ranking ni autorización semántica."""
    from .router import normalize
    # No autorizar sustitución de un documento explícito por otro de tema parecido.
    return normalize(requested).strip()==normalize(title).strip()
