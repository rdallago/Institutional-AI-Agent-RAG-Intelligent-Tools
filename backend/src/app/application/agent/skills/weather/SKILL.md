---
name: weather
description: Clima y pronostico real para una ciudad y pais explicitos.
---

Activar para clima o pronostico, incluyendo seguimiento de la ultima ubicacion
de esta conversacion autorizada. Requiere ciudad, pais ISO2 y region cuando haya
homonimos. Solo tool consultar_clima, geocoding y forecast fijos de Open-Meteo.
Si falta ubicacion o hay varias coincidencias pedir aclaracion, sin escoger una.
No inventar datos, temperatura o fechas. Los fallos de red son indisponibilidad.
Mostrar condiciones, grados Celsius, fecha/hora y zona de referencia, atribucion.
No usar un LLM para completar valores ni guardarlos como recuerdos personales.
En AUTO el planificador semántico propone los argumentos; Python valida su
esquema y Open-Meteo confirma ubicación y pronóstico. Un cambio de tema no hereda
esta herramienta: la pregunta actual prima sobre el historial. No completar
ubicaciones inciertas por intuición; pedir aclaración si faltan datos reales.
Resolver hoy, mañana y pasado mañana con fecha local de la ubicación. Aceptar
fechas explícitas y consultar hasta 16 días incluyendo hoy. Fuera de horizonte
o sin valores disponibles explicar la limitación, sin pedir ubicación ya conocida.

La politica estructurada siguiente es aplicada por la tool, no solo documentada.
No puede relajar los controles implementados en codigo.

<!-- runtime -->
{"require_country":true,"include_reference_time":true,"include_attribution":true,"invent_values":false,"max_horizon_days":15}
<!-- /runtime -->
