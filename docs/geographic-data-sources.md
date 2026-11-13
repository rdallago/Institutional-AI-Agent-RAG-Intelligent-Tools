# Datos de normalización geográfica

Snapshot local generado el 4 de noviembre de 2026, sin dependencias instaladas
ni consultas de red al arrancar la aplicación. 249 países/territorios asignados
ISO 3166-1, con alpha-2, alpha-3 y nombres/alias en español e inglés. No incluye
macroregiones CLDR ni códigos no asignados como países ISO.

Fuentes:

- [Tabla ISO 3166-1 distribuida por pycountry/iso-codes](https://github.com/pycountry/pycountry/blob/main/src/pycountry/databases/iso3166-1.json).
- [Nombres Unicode CLDR en español](https://github.com/unicode-org/cldr-json/blob/main/cldr-json/cldr-localenames-full/main/es/territories.json).
- [Nombres Unicode CLDR en inglés](https://github.com/unicode-org/cldr-json/blob/main/cldr-json/cldr-localenames-full/main/en/territories.json).

La tabla derivada está en application/agent/countries_data.py. Se conservaron
las licencias en geographic-data-pycountry-LICENSE.txt y
geographic-data-unicode-LICENSE.txt, en esta carpeta. Las URLs main identifican
la procedencia; el runtime usa exclusivamente el snapshot local, sin actualizarlo
automáticamente. Una actualización requiere revisar cambios y ejecutar pruebas.

No es un NER ni un registro de ciudades/provincias: identifica nombres/códigos
explícitos de países y exige verificación posterior mediante el geocodificador.
Ante nombres solapados toma el nombre más largo; ante varios países o ubicación
no comprobable solicita aclaración. No hay fuzzy matching para corregir países.
