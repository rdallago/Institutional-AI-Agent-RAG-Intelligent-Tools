from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictStr


class ConsultaSolicitud(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: SecretStr = Field(repr=False, description='Consulta de hasta 1000 puntos Unicode y 3000 bytes UTF-8.')


class ConsultaRespuesta(BaseModel):
    model_config = ConfigDict(extra='forbid')
    respuesta: StrictStr = Field(repr=False)
    finalizacion: Literal['completa', 'limite']
