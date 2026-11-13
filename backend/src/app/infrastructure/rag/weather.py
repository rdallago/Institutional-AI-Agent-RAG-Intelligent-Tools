"""Open-Meteo fijo; no recibe URL, identidad, historial ni credenciales."""
import asyncio
import json
import math
import re
from datetime import datetime, timezone, timedelta, date
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict

from app.application.agent.context import AgentResult
from app.application.agent.router import normalize
from app.application.agent.tools import WeatherArgs
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida, IATiempoAgotado


class WeatherPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    require_country: Literal[True]
    include_reference_time: Literal[True]
    include_attribution: Literal[True]
    invent_values: Literal[False]
    max_horizon_days: Literal[15]


CONDITIONS = {0:'despejado',1:'mayormente despejado',2:'parcialmente nublado',3:'cubierto',
    45:'niebla',48:'niebla con escarcha',51:'llovizna ligera',53:'llovizna moderada',55:'llovizna intensa',
    56:'llovizna helada ligera',57:'llovizna helada intensa',61:'lluvia ligera',63:'lluvia moderada',
    65:'lluvia intensa',66:'lluvia helada ligera',67:'lluvia helada intensa',71:'nieve ligera',
    73:'nieve moderada',75:'nieve intensa',77:'granos de nieve',80:'chubascos ligeros',81:'chubascos moderados',
    82:'chubascos intensos',85:'chubascos de nieve ligeros',86:'chubascos de nieve intensos',
    95:'tormenta',96:'tormenta con granizo ligero',99:'tormenta con granizo intenso'}


def normalized_region(value):
    value=' '.join(normalize(value).split())
    value=re.sub(r'^(?:provincia|province|estado|state|departamento|region)(?: de| of)?\s+', '', value)
    return re.sub(r'\s+(?:province|state)$','',value).strip()


class OpenMeteo:
    def __init__(self, *, transport=None, clock=None, observe_geography=None):
        self.client = httpx.AsyncClient(trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(5, connect=3), transport=transport,
            headers={'Accept-Encoding':'identity'}, limits=httpx.Limits(max_connections=1))
        self.day, self.calls = datetime.now(timezone.utc).date(), 0
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.observe_geography=observe_geography

    async def close(self): await self.client.aclose()

    async def get(self, url, params):
        today=datetime.now(timezone.utc).date()
        if today!=self.day:self.day,self.calls=today,0
        if self.calls>=4000:raise IANoDisponible()
        self.calls+=1
        try:
            async with self.client.stream('GET', url, params=params) as response:
                if response.status_code != 200: raise IANoDisponible()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data)>65536: raise IARespuestaInvalida()
                from app.infrastructure.llm.ollama import _object, _constant
                result = json.loads(data, object_pairs_hook=_object, parse_constant=_constant)
                if type(result) is not dict: raise IARespuestaInvalida()
                return result
        except httpx.TimeoutException: raise IATiempoAgotado() from None
        except httpx.HTTPError: raise IANoDisponible() from None
        except (IANoDisponible, IARespuestaInvalida): raise
        except Exception: raise IARespuestaInvalida() from None
        finally:
            self.client.cookies.clear()

    async def execute(self, args: WeatherArgs, instructions):
        try:
            WeatherPolicy.model_validate_json(instructions)
        except Exception: raise IANoDisponible() from None
        async with asyncio.timeout(12):
            return await self._execute(args)

    async def _execute(self, args):
        query = args.ciudad
        geo = await self.get('https://geocoding-api.open-meteo.com/v1/search',
            {'name':query, 'countryCode':args.pais, 'count':10, 'language':'es', 'format':'json'})
        locations = geo.get('results', [])
        if geo.get('error'): raise IARespuestaInvalida()
        if type(locations) is not list or len(locations)>10: raise IARespuestaInvalida()
        matches = [r for r in locations if type(r) is dict and str(r.get('country_code','')).upper() == args.pais
                   and ' '.join(normalize(str(r.get('name',''))).split()) == ' '.join(normalize(args.ciudad).split())
                   and (not args.region or normalized_region(str(r.get('admin1',''))) == normalized_region(args.region))]
        from app.application.agent.diagnostics import record_private
        record_private('weather_geocoding', arguments=args.model_dump(), match_count=len(matches),
                       reason='unique' if len(matches)==1 else 'no_match' if not matches else 'ambiguous')
        if self.observe_geography is not None:
            self.observe_geography({'stage':'geocoding','match_count':len(matches),'country':args.pais})
        # No tomar la primera ciudad homonima ni considerar un error como clima vacio.
        if len(matches) != 1:
            return AgentResult(strategy='TOOL', status='ACLARACION',
                answer='No pude identificar una ubicación única. Indicá ciudad, provincia o región y país.', tool='consultar_clima')
        place = matches[0]
        lat, lon = place.get('latitude'), place.get('longitude')
        if (type(lat) not in (int,float) or type(lon) not in (int,float)
            or not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180):
            raise IARespuestaInvalida()
        data = await self.get('https://api.open-meteo.com/v1/forecast',
            {'latitude':lat,'longitude':lon,'current':'temperature_2m,weather_code',
             'daily':'weather_code,temperature_2m_max,temperature_2m_min',
             'timezone':'auto','forecast_days':16,'temperature_unit':'celsius'})
        try:
            offset = data['utc_offset_seconds']
            zone = data['timezone']
            if type(offset) is not int or not -50400<=offset<=50400 or not isinstance(zone,str) or len(zone)>80:
                raise ValueError()
            now = self.clock().astimezone(timezone(timedelta(seconds=offset)))
            expected = (date.fromisoformat(args.fecha) if args.fecha else
                        now.date()+timedelta(days={'hoy':0,'mañana':1,'pasado mañana':2}[args.dia]))
            delta = (expected-now.date()).days
            if not 0<=delta<=15:
                return AgentResult(strategy='TOOL', status='HERRAMIENTA', tool='consultar_clima',
                    answer=f'No hay pronóstico disponible para {expected.isoformat()}. El horizonte consultable va de {now.date().isoformat()} a {(now.date()+timedelta(days=15)).isoformat()} ({zone}).',
                    tool_context=args.model_dump())
            if args.dia == 'hoy':
                current = data['current']; stamp = current['time']
                reference = datetime.fromisoformat(stamp).replace(tzinfo=now.tzinfo)
                if abs((now-reference).total_seconds()) > 10800: raise ValueError()
                temperature, code = current['temperature_2m'], current['weather_code']
                if data['current_units']['temperature_2m'] != '°C': raise ValueError()
                text = f'{self.temperature(temperature):g} °C, {self.condition(code)}. Referencia: {stamp} ({zone}).'
            else:
                daily = data['daily']
                times = daily['time']
                if (type(times) is not list or not 1<=len(times)<=16
                    or times != [(now.date()+timedelta(days=i)).isoformat() for i in range(len(times))]): raise ValueError()
                for field in ('temperature_2m_min','temperature_2m_max','weather_code'):
                    if type(daily[field]) is not list or len(daily[field])!=len(times): raise ValueError()
                if data['daily_units']['temperature_2m_max']!='°C' or data['daily_units']['temperature_2m_min']!='°C': raise ValueError()
                if expected.isoformat() not in times or any(daily[field][delta] is None for field in ('temperature_2m_min','temperature_2m_max','weather_code')):
                    return AgentResult(strategy='TOOL', status='HERRAMIENTA', tool='consultar_clima',
                        answer=f'El proveedor no tiene pronóstico disponible para {expected.isoformat()} ({zone}). No se estimaron valores.',
                        tool_context=args.model_dump())
                low, high = self.temperature(daily['temperature_2m_min'][delta]), self.temperature(daily['temperature_2m_max'][delta])
                if low>high: raise ValueError()
                text = f'Pronóstico {expected.isoformat()} ({zone}): mínima {low:g} °C, máxima {high:g} °C, {self.condition(daily["weather_code"][delta])}.'
            label = ', '.join(filter(None,[str(place['name']),str(place.get('admin1','')),args.pais]))
            if len(label)>220 or any(c in label for c in '\x00\r\n'): raise ValueError()
        except Exception: raise IARespuestaInvalida() from None
        return AgentResult(strategy='TOOL', status='HERRAMIENTA',
            answer=f'{label}: {text} Datos y pronóstico por Open-Meteo.com (CC BY 4.0). Ubicación: GeoNames.',
            tool='consultar_clima', tool_context=args.model_dump())

    @staticmethod
    def temperature(value):
        if type(value) not in (int,float) or not math.isfinite(value) or not -100<=value<=70:
            raise ValueError()
        return value

    @staticmethod
    def condition(code):
        if type(code) is not int or code not in CONDITIONS: raise ValueError()
        return CONDITIONS[code]
