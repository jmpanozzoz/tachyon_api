> Historical snapshot from an earlier audit/repair stage. Its counts, pending actions and source references describe that stage. For the published 1.4.0 state, see [local release validation](LOCAL_RELEASE.md) and the [verified publication receipt](local-release/publication.json).

# Implementación del plan 1.4.0

Estado al 2026-11-04: versión **1.4.0 preparada y validada localmente**, sin commit, merge, tag ni publicación. El informe AUDITORIA.md y sus resultados originales se conservan como registro histórico de 1.3.1.

## Resultado

Se implementaron las correcciones de los hallazgos A01–A21 y las acciones concretas de simplificación, DX y distribución. Las decisiones de producto se cerraron de forma explícita: servidor estándar, ejecución sync en threads, rango Python validado, OpenAPI 3.0 con rechazo de formas no representables y dependencias de instalación base conservadas. No se agregaron TUI, migrador ni subsistemas nuevos.

### Trazabilidad

| Auditoría | Implementación |
|---|---|
| A01 | Guards de router, include y ruta acumulados; un solo cache de dependencias; Depends sin callable falla al registrar |
| A02, A16 | Retirados writer, extensión y wire helpers; fachada server.run/TachyonHTTPProtocol usa Uvicorn estándar |
| A03 | Redis clear no escala a flushall |
| A04, A05 | Contenedores ASGI y headers por envío; bytes de error compartidos, Response mutable por solicitud |
| A06, A07 | Recepción limitada acumulativamente; una sola Request y cache de body, también para exception handlers |
| A08, A09 | Binding seguro positional/keyword, validación de firmas y opciones, sin cache global de endpoints |
| A10–A12 | Unicode por caracteres, nombres de parámetros por ruta/método y fallback tras prefijo estático incompleto |
| A13 | Firmas resueltas al registrar y compartidas por compilación, DI, WebSocket y OpenAPI; compatibilidad Python 3.10 |
| A14 | Conversión/validación de Form, aliases y listas |
| A15 | Resolver explícito para WebSocket; cache por conexión y guards del router |
| A17 | Background después del body; wrapper propio por solicitud sin modificar respuestas reutilizadas |
| A18 | Tracebacks en errores no manejados; transmisión fuera del try que convierte excepciones en respuestas |
| A19 | Eliminada la preconversión mutante de payloads |
| A20 | Estado yielded del lifespan propagado; shutdown en finally |
| A21 | FormData cerrado después de respuesta/tareas; formularios limitados y bufferizados antes de parsear; cierre de handles incompletos |
| P01 | Tablas inmutables acotadas a 1.024 longitudes |
| P02 | Offload de código sync, scopes/overrides preservados y construcción concurrente de singleton protegida |
| P03 | Benchmark async equivalente, ASGI base, validación de cada respuesta y resultados por escenario/repetición |
| P04 | Cache en memoria acotado, monotónico y protegido por lock; configuración explícita opcional y semántica global documentada |
| P05 | Importación del runtime sin cargar Uvicorn |
| D01 | Schemas de msgspec adaptados, wire names/defaults/herencia/nullabilidad y colisiones rechazadas |
| D02 | Guía cache reescrita contra API real y límites de adaptadores documentados |
| D03 | Bloques administrados preservan instrucciones; referencias dinámicas de API/CLI/templates y consejo async corregido |
| D04 | no-fix no formatea; OpenAPI CLI identificado como chequeo estructural limitado |
| D05 | option=0 respetado, decode genérico validado y booleanos inválidos rechazados |
| D06 | Backend setuptools con metadata Poetry; wheel portable real y extras coherentes |
| D07 | Matriz min/max Python en ambos motores, Ruff, smoke conductual de wheels, rebuild del sdist y coverage del fallback |
| D08 | Cliente async unificado; contrato de lifespan/dependencias de testing documentado; guía del repositorio actualizada |

Se retiraron también los parsers numéricos C que truncaban enteros grandes o aceptaban entradas distintas de Python. Los tests incluyen enteros fuera de long, dígitos Unicode, espacios y separadores.

## Validación ejecutada

[validation-1.4.0.json](validation-1.4.0.json) conserva versiones y resultados:

- Python 3.10.22, fallback: **473 passed**.
- Python 3.10.22, Cython: **473 passed**.
- Python 3.13.18, fallback: **473 passed**.
- Python 3.13.18, Cython: **473 passed**.
- Python 3.13 + Starlette 1.10.0, Cython: **473 passed**. Las demás ejecuciones usaron Starlette 1.3.1.
- Wheel `py3-none-any` instalado fuera del checkout: **82 contratos passed**.
- Sdist reconstruido a wheel nativo CPython 3.13 ARM64, instalado fuera del checkout: **82 contratos passed**.
- Paridad: **26 pares, 26 extensiones**, alineados.
- Ruff y `git diff --check`: pasan.
- Schemas completos del benchmark y del ejemplo comprobados con openapi-spec-validator externo al runtime: válidos.
- Benchmark final fallback: **48 mediciones, 9.600 respuestas medidas y validadas, cero errores**. Ver [datos originales](../../../benchmark/results/1.4.0-python.json).

Las ejecuciones no sustituyen a los jobs Linux/Windows ni a toda la matriz de wheels de CI. No se ejecutó publicación o integración con Redis/Memcached reales. Las advertencias restantes son deprecaciones de dependencias y fechas UTC del ejemplo; no se presentan como ausencia total de deuda.

### Memoria y rendimiento

En el mismo Python 3.13 y con el runtime Python:

| Medición de importación | Antes | Después |
|---|---:|---:|
| Bytes retenidos trazados por Python | 28.133.797 | 10.067.161 |
| Diccionarios/tablas de headers, tamaño superficial | 5.243.056 | 16.464 |
| Asignaciones retenidas atribuidas al módulo de headers | ~14,8 MiB | 110.775 bytes |
| Uvicorn cargado al importar Tachyon | Sí | No |

Esto representa aproximadamente **64 % menos bytes Python trazados al importar** y más de **99 % de reducción en las asignaciones del cache de headers**. No es RSS, tamaño de instalación ni una promesa por worker; no se usa el tiempo bajo tracemalloc como benchmark de latencia normal. Evidencia: [antes](import-python.json), [después](import-1.4.0-python313.json).

Las correcciones del trie tienen costo: el microbenchmark Python retenido mide aproximadamente +103 ns en `/hello` y +366 ns en `/users/42/profile`. El thread pool agrega scheduling a handlers sync triviales. Estos costos se conservan explícitamente; no se afirma que todos los endpoints sean más rápidos. El benchmark de red es loopback con cliente Python, incluye validación y conexión, y no aísla overhead puro. No se suman tasas ni se publica un nuevo multiplicador frente a FastAPI.

[Medición de tamaño fuente](source-size-1.4.0.json) permite distinguir código del runtime de tests/evidencias añadidos. Se simplificaron factories, dispatch, respuestas, servidor y build, conservando APIs públicas donde era razonable.

## Revisión EGM

Se usaron revisores con contexto de conversación nuevo para runtime y para DX/distribución, siguiendo el patrón EGM de revisión adversarial adaptado a código. Ambos completaron su lectura y produjeron hallazgos accionables.

La revisión detectó, y se corrigió con regresiones:

1. Guard del router reemplazado por dependencias específicas de ruta.
2. Archivos incompletos sin cierre al desconectar durante multipart.
3. Repetición de tareas al reutilizar una Response.
4. Request sin límite/cleanup en exception handlers del camino rápido.
5. Preparación de dependencias de clase omitida en el compilador Cython.
6. Schemas corruptos por propiedades llamadas como keywords de JSON Schema.
7. Colisiones de nombres de componentes y límites exclusivos incompatibles con OpenAPI 3.0.

Una revisión posterior, también con contexto nuevo, leyó los contratos corregidos y ejecutó **81 tests dirigidos**, sin confirmar nuevos bloqueantes. Luego se completaron las suites y comprobaciones de artefactos descritas arriba. Esto no equivale a demostrar convergencia del flujo documental EGM ni corrección exhaustiva.

## Decisiones y límites para la release

- La compatibilidad del servidor conserva los puntos de entrada, no la escritura insegura.
- Python 3.14 queda excluido hasta validar una actualización de msgspec. Se mantienen msgspec 0.19.0 y el contrato explícito de 3.10–3.13.
- OpenAPI soporta 3.0.x; modelos con nombres incompatibles o schemas no representables se rechazan al registrar. La validación runtime puede usarse con `include_in_schema=False`.
- Se mantienen orjson y msgspec. No se eliminó un serializer sin medir y preservar opciones/tipos/wire JSON.
- Se conservan las dependencias base de CLI/server/form para no romper instalación y ejemplos. Los imports del servidor ya están separados del runtime, y separar extras queda como decisión futura de distribución.
- La configuración global de cache mantiene semántica de captura al decorar; `config=` permite aislamiento explícito. No hay serialización automática universal para clientes externos.
- Las dependencias con yield no se implementan; se rechazan en startup y se indica usar lifespan.
- Pendiente operativo: ejecutar CI alojado en plataformas soportadas, revisar el diff y hacer el flujo de merge/publicación del repositorio. No se ejecutaron esas acciones en esta sesión.

La [guía de migración](../../17-migration-1.4.md) explica los cambios observables. CHANGELOG.md incluye la entrada 1.4.0.
