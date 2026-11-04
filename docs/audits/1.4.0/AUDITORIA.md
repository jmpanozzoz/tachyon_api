> Historical snapshot from an earlier audit/repair stage. Its counts, pending actions and source references describe that stage. For the published 1.4.0 state, see [local release validation](LOCAL_RELEASE.md) and the [verified publication receipt](local-release/publication.json).

# Auditoría de Tachyon API para preparar 1.4.0

Fecha: 2026-11-04. Base: `1b89bf134a1a418145c200162c4ca4d5dded46a6`, versión declarada 1.3.1.

**Estado: auditoría, sin cambios de implementación ni de versión.** Las correcciones y eliminaciones siguientes son propuestas. No se publicó, commiteó ni etiquetó una release.

## Dictamen

Antes de perseguir otro multiplicador frente a FastAPI, hay que corregir contratos observables de Tachyon. Una dependencia de autorización declarada en un Router no se ejecuta; el servidor propio puede saltarse middleware; los 404 con CORS fallan; los 500 conservan headers entre solicitudes. Son problemas que bloquean recomendar 1.4.0 como release estable.

La arquitectura conserva decisiones útiles: compilar metadatos al registrar rutas, validar con msgspec, serializar Struct directamente y delegar WebSocket/lifespan en Starlette. El problema está en varias optimizaciones y abstracciones alrededor: duplican contratos, comparten objetos mutables o eliminan trabajo necesario para ofrecer la semántica anunciada.

La oportunidad más clara para adelgazar el producto está medida: los caches de Content-Length retienen aproximadamente **14,8 MiB de asignaciones Python al importar**. No hace falta un motor nuevo para mejorar eso. Tampoco hace falta ampliar el CLI antes de corregir sus operaciones destructivas y su documentación.

## Método y evidencia

Se aplicó el patrón Elephant & Goldfish: tres revisores con conversación nueva e independiente, seguidos de consolidación y comprobación por el agente principal. Áreas: runtime/DI/parámetros; routing/servidor/ASGI; diseño/packaging/DX. Los tres completaron su revisión. Se utilizaron las personas `codebase_details` y `design_critic` del plugin EGM. Esto fue una auditoría de código adaptada al patrón, **no** una ejecución del flujo documental de cinco fases ni una declaración de convergencia de ese flujo. El aislamiento de instrucciones del entorno no fue verificado.

Se consultó Context7 para Starlette, msgspec 0.19.0 y Uvicorn. La documentación actual se contrastó con el código local y las versiones instaladas; no se asumió que `main` de una dependencia describe exactamente la versión fijada.

| Verificación | Resultado |
|---|---|
| Suite original, Python 3.13.18, fallback Python | 359 passed |
| Compilación local de las 27 extensiones | Completada |
| Suite original, mismo Python, Cython 3.3.1 | 359 passed |
| Suite del ejemplo, fallback Python, con PyJWT | 17 passed |
| Paridad estructural | 26 pares alineados; 27 `.pyx` |
| Reproducciones adicionales | 21 escenarios ejecutados en ambos modos |
| Ruff 0.14.9, `tachyon_api tests` | 25 avisos: 17 F401 y 8 E731 |
| Wheel con `TACHYON_SKIP_CYTHON=1` | Construido; sin `.so`, pero con tag específico de CPython/plataforma |

Entorno: macOS ARM64, Starlette 1.3.1, msgspec 0.19.0, orjson 3.11.1 y Uvicorn 0.35.0. [environment.json](environment.json) enumera las dependencias de la sesión; no representa una instalación exacta desde `poetry.lock`.

Evidencia conservada:

- [probes.py](probes.py): reproducciones autocontenidas; registran el comportamiento actual, no son tests de aceptación.
- [probes-python.json](probes-python.json) y [probes-compiled.json](probes-compiled.json): resultados originales con identificación del módulo importado.
- [measure_import.py](measure_import.py) e [import-python.json](import-python.json): medición de asignaciones de importación.
- [additional-checks.json](additional-checks.json): comprobaciones adicionales de CLI, OpenAPI y helpers. Las operaciones de escritura del CLI se comprobaron en un directorio temporal o con subprocess simulado.

Alcance: código de aplicación, routing, procesamiento y extractores Python/Cython, DI, respuestas, middleware, seguridad, OpenAPI, CLI/templates, testing, ciclo de vida, WebSocket, caché, packaging, CI, benchmark y ejemplo. No se afirma cobertura exhaustiva de todas las combinaciones posibles. No se hicieron pruebas de carga por red, fuzzing, pruebas Windows/Linux, auditoría de CVEs actuales ni explotación con un navegador. Los probes de transporte usan un ciclo simulado; no prueban todas las condiciones de una conexión real.

## Prioridad de los hallazgos

P0: posible pérdida de datos o controles de seguridad omitidos. P1: comportamiento incorrecto que debe resolverse antes de una release estable. P2: DX, consumo o mantenimiento que requiere un cambio planificado. La prioridad depende del uso: los fallos del servidor experimental requieren activar ese servidor.

### A01 · P0 · Las dependencias declaradas en Router no se ejecutan

**Evidencia:** `router.py:50`, `app/__init__.py:204`, `app/_route_installer.py:25`, `processing/compiler.py:106`.

`Router(dependencies=[Depends(reject)])` conserva el dato en el registro; el instalador y el compilador no lo incorporan a la ejecución. Una dependencia que levanta HTTPException(401) registra **cero llamadas** y el endpoint devuelve **200 con el contenido protegido**. Probe `ignored_dependencies`, reproducido en ambos modos.

**Propuesta:** ejecutar dependencias de ruta/router con el mismo contexto por solicitud o rechazar explícitamente esa configuración hasta implementarla. Nunca aceptar silenciosamente una opción que parece aplicar autorización. Aclarar también qué argumentos de `include_router(**kwargs)` se soportan: actualmente se aceptan y no se consumen.

### A02 · P0 · El servidor propio saltea middleware de respuesta

**Evidencia:** `app/_fast_asgi_factory.py:40`, `processing/dispatch.py:92`, sus equivalentes Cython y `server.py:39`.

La escritura directa al transporte evita el `send` envuelto por middleware. El probe `middleware_bypass` produce una respuesta, **cero eventos ASGI send** y ningún header CORS, aunque el origen está permitido. Comprobado en ambos modos. Por el mismo mecanismo quedan fuera transformaciones implementadas mediante `send`, como headers de seguridad, compresión o cookies de sesión. Es una inferencia del mecanismo; no se probaron individualmente todos esos middleware.

**Propuesta:** desactivar esa vía o retirarla del producto estable. Conservarla exigiría demostrar elegibilidad después de todas las transformaciones y mantener pruebas de protocolo. Su ahorro histórico en microsegundos no justifica incumplir ASGI.

### A03 · P0 · Redis clear puede escalar a borrar todas las bases

**Evidencia:** `cache.py:232`.

Ante cualquier error de `flushdb()`, el backend intenta `flushall()`. El probe con cliente simulado confirma una llamada a cada operación. No se ejecutó ninguna operación contra Redis real.

**Propuesta:** eliminar el fallback `flushall`, registrar o propagar el fallo original. Incluso `flushdb` requiere documentar que afecta toda la base configurada, no solamente claves de Tachyon.

### A04 · P1 · CORS falla en respuestas 404

**Evidencia:** `app/_error_static.py:15`, `processing/dispatch.py:54`, `middlewares/cors.py:156`.

El dispatcher envía un MappingProxyType y CORS intenta asignar `message['headers']`. Una ruta inexistente con origen permitido levanta TypeError. Probe `cors_404`, ambos modos.

**Propuesta:** mensajes y contenedores de headers propios de cada envío. Las constantes inmutables pueden seguir compartiéndose internamente.

### A05 · P1 · Los 500 comparten estado mutable entre solicitudes

**Evidencia:** `responses/_internal_error.py:34`, `:42`, su `.pyx`, `middlewares/cors.py:156`.

El singleton conserva el mensaje modificado por CORS. Secuencia medida: origen A recibe `[A]`; B recibe `[A,B]`; un origen no permitido también recibe `[A,B]`. Probe `cors_500`, ambos modos. Esto demuestra contaminación de headers y crecimiento; **no demuestra** que un navegador permita leer datos protegidos.

**Propuesta:** compartir únicamente bytes y tuplas inmutables; crear mensajes/headers por respuesta. Probar también apps distintas en el mismo proceso y respuestas cacheadas por el usuario.

### A06 · P1 · El límite de body no limita la memoria consumida

**Evidencia:** `processing/scope.py:75`, `_extractors/body.py:27`, `parameters.py:118`, y sus `.pyx`.

JSON se almacena completo antes de comprobar su longitud real. Con límite de 4 bytes se consumen cinco chunks de 5 bytes antes del 422. Los formularios ni siquiera pasan por ese control: un campo de 1.000 caracteres devuelve 200 con el mismo límite. Probes `chunk_limit` y `form_limit_and_type`, ambos modos.

**Propuesta:** límite acumulativo al recibir, compartido por JSON, Request, formularios y archivos; cortar antes de almacenar el siguiente chunk. Definir y documentar el código de error. Los límites propios del parser multipart complementan este control, no lo reemplazan.

### A07 · P1 · Body y Request compiten por el mismo stream

**Evidencia:** `processing/scope.py:75` y `:96`, también `.pyx`.

TachyonScope y Request mantienen caches de body separados. Si un endpoint declara `request: Request` y `data: dict = Body()` y luego hace `await request.body()`, la solicitud queda esperando otra lectura. El probe `request_body` agota un timeout de 0,5 segundos en ambos modos.

**Propuesta:** una sola fuente de verdad para consumo/cache del stream, incluida la lectura desde dependencias. Probar ambos órdenes de lectura, desconexión y multipart.

### A08 · P1 · La invocación posicional corrompe firmas válidas

**Evidencia:** `processing/compiler.py:115`, `response_processor.py:47`, equivalentes Cython.

`def endpoint(*, q: int = Query(...))` devuelve 500. `def endpoint(x=10, q: int = Query(...))` recibe `x=3` y el objeto Query original en `q` al pedir `?q=3`: responde 200 con argumentos incorrectos. Probes `keyword_only` y `shifted_default`, ambos modos.

**Propuesta:** determinar al registrar si la llamada posicional es segura. Preservar binding por nombre cuando existan huecos/defaults o parámetros keyword-only. Rechazar firmas no soportadas al registrar, con un mensaje útil.

### A09 · P1 · La caché del compilador ignora el path

**Evidencia:** `processing/compiler.py:103`, `:108`, `:160`, y `.pyx`.

El análisis infiere parámetros desde el path pero cachea únicamente por función. Compilar la misma función para `/fixed` y luego `/{x}` devuelve el mismo objeto con cero parámetros. Probe `path_cache`, ambos modos. Además, la caché global retiene funciones indefinidamente.

**Propuesta:** separar metadatos de firma y metadatos de ruta, o quitar la caché global: el resultado ya queda retenido en el handler y la compilación es trabajo de registro. Medir startup antes de introducir otra caché.

### A10 · P1 · Cython rompe rutas Unicode

**Evidencia:** `routing/trie.pyx:98` y `:110`.

Se escanean bytes UTF-8 y se usan esos offsets para cortar un str por caracteres. `/café/niño` devuelve 200 con `name='niño'` en Python y 404 compilado. Probe `unicode_route`; **verificado ejecutando la extensión real**, no solamente por lectura.

**Propuesta:** mantener una unidad de indexación consistente. Conservar el recorrido ASCII optimizado solamente si existe una alternativa Unicode probada y el beneficio se mide.

### A11 · P1 · El trie comparte nombres de parámetros entre rutas

**Evidencia:** `routing/trie.py:62`, `:120`, y `.pyx`.

GET `/names/{id}` seguido de POST `/names/{name}` conserva `id` en el nodo compartido. POST `/names/alice` responde 200 con `name=null`. Probe `route_names`, ambos modos.

**Propuesta:** asociar nombres a la ruta terminal/método, o rechazar conflictos explícitamente. No permitir que el orden de registro cambie silenciosamente los argumentos.

### A12 · P1 · Un prefijo estático bloquea rutas dinámicas válidas

**Evidencia:** `routing/trie.py:114`, equivalente `.pyx`.

Con `/users/{id}/posts` y `/users/admin/settings`, `/users/admin/posts` devuelve 404: el matcher elige `admin` y no recupera la alternativa dinámica cuando el resto falla. Probe `route_backtrack`, ambos modos.

**Propuesta:** definir prioridad entre coincidencias completas y hacer backtracking limitado. Si se prefiere prohibir esa combinación por simplicidad, detectarla en startup. La complejidad real debe documentarse después de elegir esa semántica.

### A13 · P1 · Las anotaciones pospuestas no se resuelven

**Evidencia:** `processing/compiler.py:112`, `:116`, `_sig_cache.py:22`, y compilador Cython.

Un módulo con `from __future__ import annotations` y `q: int = Query(...)` devuelve 422 para `q=3`: conserva `'int'` como string. Probe `postponed_annotations`, ambos modos. Los checks por identidad para Request/BackgroundTasks/DI también dependen de tipos resueltos.

**Propuesta:** resolver anotaciones al registrar y definir un error de startup para referencias no resolubles. Compartir esa resolución con DI, WebSocket y OpenAPI; evitar cuatro implementaciones divergentes.

### A14 · P1 · Los campos Form no respetan su tipo declarado

**Evidencia:** `processing/_extractors/form.py:15` y `.pyx`.

`n: int = Form(...)` recibe una cadena arbitraria y devuelve 200. El probe combinado confirma `type='str'` para un campo de 1.000 caracteres.

**Propuesta:** reutilizar metadatos de conversión compilados para escalares/listas. Probar errores, aliases, defaults y archivos enviados donde se espera un campo.

### A15 · P1 · WebSocket pierde acceso al resolver de Tachyon

**Evidencia:** `app/_asgi_entry.py:30`, `core/websocket.py:68` y `:98`.

El flujo delega en Starlette, que vuelve a establecer `scope['app']` con su propia instancia. El WebSocket busca allí `_dependency_resolver` y no lo encuentra. El probe `websocket_di` recibe el objeto Depends original en lugar de `'ready'`, tanto en Python como con extensiones.

**Propuesta:** vincular explícitamente el resolver o preservar la referencia de Tachyon bajo una clave interna estable. Pasar el cache de conexión también a las dependencias de clase y especificar qué significa scope request para WebSocket.

### A16 · P1 · El servidor propio incumple HEAD y pierde headers

**Evidencia:** `server.py:47`, `_server_fast.pyx:77`.

El probe `direct_write` confirma body en una respuesta HEAD y ausencia de un header agregado a `response.headers`. Ocurre en ambos modos. El writer arma Content-Length/Content-Type por separado e ignora `raw_headers`.

Además, el compilado pierde `server: audit` cuando no existe Date. `_get_default_bytes`, `_server_fast.pyx:34`, considera un Date vacío igual al cache inicial y devuelve bytes vacíos. El key tampoco distingue configuraciones con la misma fecha.

**Propuesta:** retirar/desactivar el writer antes de estabilizar 1.4.0. Si permanece, cubrir HEAD, 204/304, cookies, keep-alive, pipelining, errores y flow control con sockets reales. La omisión de body en HEAD está documentada por [Uvicorn](https://github.com/kludex/uvicorn/blob/main/docs/server-behavior.md).

### A17 · P1 · BackgroundTasks corre antes de enviar la respuesta

**Evidencia:** `processing/response_processor.py:23`, `.pyx:19`.

Orden medido: `background`, `http.response.start`, `http.response.body`. Probe `background_order`, ambos modos. Contradice la descripción pública y aumenta el tiempo hasta la respuesta.

**Propuesta:** ejecutar después del último body enviado, preservando tareas de una Response existente. Adaptar también los envíos inline: arreglar únicamente Response.__call__ dejaría parte del problema activo.

### A18 · P1 · Los errores no manejados pueden quedar sin traceback

**Evidencia estática:** `app/_fast_asgi_factory.py:55`, `app/_handler_factory.py:63`.

Se convierten excepciones en 500 sin log ni propagación; HTTP evita el middleware de errores de Starlette. En el camino rápido el try también cubre la transmisión: un fallo después de iniciar la respuesta puede provocar un intento de segundo response.start.

**Propuesta:** un contrato único de errores, log con traceback y separación entre ejecutar el endpoint y transmitir. No se hizo una prueba completa de desconexión por red; ese extremo requiere validación adicional.

### A19 · P2 · La serialización modifica objetos del usuario

**Evidencia:** `processing/response_processor.py:39`, equivalente `.pyx`.

Un dict compartido con un Struct termina guardando un dict en esa posición después de responder. Probe `payload_mutation`, ambos modos. El helper de orjson ya sabe convertir Struct mediante default; el preprocesamiento es redundante y cambia estado visible, especialmente si el payload está cacheado.

**Propuesta:** eliminar la mutación previa, manteniendo compatibilidad de los JSON generados.

### A20 · P2 · Lifespan descarta el estado yielded

**Evidencia:** `core/lifecycle.py:34`.

Un lifespan que hace `yield {'db':'ready'}` produce `request.state.db == 'MISSING'`. Probe `lifespan_state`, ambos modos. Los tests existentes comprueban app.state, que es otro mecanismo.

**Propuesta:** propagar el valor yielded y probar apertura/cierre con errores. Conservar Starlette como propietario del protocolo.

### A21 · P2 · Falta cierre explícito de formularios/UploadFile

**Evidencia:** `processing/scope.py:88`, `app/_handler_factory.py:36` y ausencia de cleanup del FormData.

El revisor de runtime comprobó que un UploadFile retenido después de un 200 sigue con `file.closed=False`. La finalización del objeto puede cerrar recursos si nada lo retiene; por eso no se afirma una fuga incondicional en cada solicitud. Ese escenario no está en los 21 probes conservados.

**Propuesta:** cerrar FormData al finalizar respuesta y tareas asociadas, con finally también en validaciones fallidas. Establecer explícitamente la vida útil permitida para los archivos.

## Rendimiento y tamaño

### P01 · Las tablas de Content-Length dominan la memoria de importación

`responses/_caches.py:10` y `:23` crean dos diccionarios de 65.536 entradas. Tracemalloc atribuye al archivo **14,8 MiB y 261.632 asignaciones retenidas**; el tamaño superficial de los dos diccionarios suma 5.243.056 bytes. El comentario de aproximadamente 512 KB subestima el costo.

La importación completa retuvo 28.133.797 bytes trazados en una ejecución. Son asignaciones Python, **no RSS ni memoria incremental exacta de un worker**, y el tiempo de 575 ms incluye tracing e instrumentación: no debe publicarse como latencia de importación normal.

**Propuesta:** comparar cache pequeño e inmutable contra conversión directa; elegir con mediciones de importación, memoria y respuestas de distintos tamaños. No reemplazarlo por un cache sin límite que vuelva a crecer bajo tráfico.

### P02 · Los endpoints sync corren directamente en el event loop

`response_processor.py:55`, `.pyx`, `background.py:31` y `_callable_factory.py:64` ejecutan código síncrono inline. Una operación bloqueante detiene el worker. El constructor de dependencias y los exception handlers sync también requieren una política explícita.

Esto es una decisión de ejecución que afecta el contrato, no una ganancia gratuita. [Starlette documenta el uso de thread pool para endpoints y tareas síncronas](https://github.com/kludex/starlette/blob/main/docs/threadpool.md). La decisión para 1.4.0 debe considerar DX, concurrencia y seguridad de las instancias compartidas. Si se conserva el modo inline, debe ser explícito y debe probarse que otro request puede progresar durante trabajo bloqueante en el modo seguro.

### P03 · El benchmark no permite afirmar un multiplicador de overhead

`benchmark/app_fastapi.py` y `app_tachyon.py` no hacen trabajo equivalente:

- Todos los endpoints principales son `def`; FastAPI normalmente los deriva al thread pool y Tachyon los ejecuta inline.
- DI crea una Database por llamada en FastAPI; Tachyon reutiliza un singleton.
- El escenario de response_model compara un dict con un Struct ya construido.
- Search acepta/valida una lista adicional solamente en FastAPI.

`run_benchmark.sh:139` suma tasas de escenarios medidos por separado. Esa suma puede ser una puntuación sintética, pero **no es capacidad observada de una aplicación**. El runner no valida cuerpos/status, descarta información de errores, tolera fallos en warmup y no solicita percentiles. También imprime plataforma/Python hardcodeados y consulta un `tachyon_api.__version__` inexistente.

**Propuesta:** baseline ASGI puro + Tachyon + FastAPI con async equivalente; separar sync/threadpool; igualar scopes y payloads; verificar respuestas; repetir mediciones y guardar resultados crudos con p50/p95/p99, errores y entorno real. No fijar “12×” como condición de release. No se ejecutó un nuevo benchmark de red ni se afirma que Tachyon sea más lento: las cifras existentes no aíslan la causa de la diferencia.

### P04 · Cachés globales y memoria sin límite

`cache.py:49` elimina una entrada vencida únicamente cuando se vuelve a pedir esa clave. Entradas vencidas de uso único permanecen si el tráfico usa claves nuevas; no hay capacidad máxima. `_COMPILED` y `_SIG_CACHE` retienen funciones globalmente. La configuración de cache también es global y los decoradores capturan su estado al decorar, aunque se configure mediante una app.

**Propuesta:** política pequeña de capacidad/expiración, TTL con reloj monotónico, configuración explícita y scope bien documentado. Para compilación, preferir retención por app/handler. No agregar un subsistema genérico de caches para resolver esto.

### P05 · La importación del framework carga el servidor experimental

`processing/dispatch.py:15` y `_fast_asgi_factory.py:16` importan server, que importa el protocolo httptools de Uvicorn. `import-python.json` confirma `uvicorn_imported=true` al importar Tachyon.

**Propuesta:** separar runtime ASGI y runner/servidor. Es un paso previo para hacer dependencias de CLI/server opcionales. Primero medir grafo y tamaño de instalación; mover dependencias sin cortar imports no funcionaría.

## DX, documentación y distribución

### D01 · OpenAPI contradice nombres y obligatoriedad reales

`openapi/_route_builder.py:111` publica `x_api_key` donde el runtime exige `x-api-key`; ignora aliases de cookie/form/file. `additional-checks.json` conserva el resultado.

`_struct_schemas.py:58` infiere required desde Optional en lugar de la presencia de defaults. Para un campo `Optional[int]` sin default y otro `int=42`, la lista required queda invertida. Tampoco representa bien campos heredados, nombres renombrados o dos Struct con el mismo nombre en módulos distintos: requiere pruebas específicas antes de fijar el alcance exacto de esos casos.

`TypeUtils.unwrap_optional`, `utils/type_utils.py:23`, reconoce typing.Union y no la unión PEP 604. El probe `schema_defaults` muestra `int | None` como string. La incompatibilidad también afecta conversión de parámetros, no solamente documentación.

**Propuesta:** utilizar metadatos/schema de msgspec cuando sea viable y adaptar al OpenAPI elegido; resolver nombres desde los mismos descriptores del runtime. No mantener un segundo sistema de tipos manual para cubrir cada nueva variante.

### D02 · La guía de cache describe otra API

`docs/07-caching.md` usa `ttl`, `key`, `condition`, `max_size`, constructores por URL y operaciones async en config que no existen. `cache.py:136` ofrece `TTL`, `key_builder`, `unless`, clientes inyectados y métodos sync del backend.

**Propuesta:** reescribir la guía contra la implementación y ejecutar sus ejemplos. No implementar las funciones imaginadas solamente para conservar ese texto. Revisar también la serialización de valores Redis: hoy el adaptador no garantiza un round trip de resultados arbitrarios de un endpoint.

### D03 · install-skill puede sobrescribir instrucciones existentes

`cli/commands/skill.py:21` escribe archivos completos; la invocación por defecto cubre varias herramientas. AGENTS.md, reglas Cursor y Copilot existentes pueden perder su contenido. La comprobación con un AGENTS.md temporal confirma que el contenido original desaparece.

`cli/templates/ai_skill.py:251` además enseña que un exception handler async bloquea y que se debe preferir sync, al revés del comportamiento real. El template es mayormente estático aunque CLAUDE.md exige introspección dinámica.

**Propuesta:** bloque administrado o archivo dedicado, preservación del contenido y reemplazo completo solamente explícito. Corregir el consejo y reducir templates repetidos; no ampliar este producto auxiliar antes de estabilizar el framework.

### D04 · lint --no-fix modifica archivos y openapi validate valida muy poco

`cli/commands/lint.py:176` llama `ruff format` sin `--check` incluso con `--no-fix`. El subprocess simulado en `additional-checks.json` conserva ambos comandos.

`cli/commands/openapi.py:110` acepta `{'openapi':123,'info':{},'paths':{}}` con exit code 0. No valida OpenAPI; comprueba unas claves.

**Propuesta:** respetar el modo de solo comprobación. Para OpenAPI, describirlo como comprobación estructural limitada o usar un validador real como dependencia opcional del CLI.

### D05 · Helpers JSON tienen comportamientos sorprendentes

`models.py:33`: `option=0` se reemplaza por los defaults al usar `option or _ORJSON_OPTS`. Se comprobó que conserva OPT_UTC_Z aun solicitando cero.

`models.py:36`: `decode_json(..., list[Example])` devuelve list[dict], sin construir ni validar Example. Solo trata especialmente un Struct directo. `additional-checks.json` conserva el tipo dict resultante.

`TypeConverter._convert_bare` convierte cualquier cadena que no reconoce como true en false: `banana` se acepta como false. Definir explícitamente el conjunto de valores booleanos válidos y devolver un error para el resto.

**Propuesta:** semántica coherente y validada, o nombres/docstrings que indiquen la limitación. No cambiar opciones del usuario por truthiness.

### D06 · El fallback y el extra fast no representan lo anunciado

`pyproject.toml:32` referencia Cython en `[fast]`, pero no lo declara como dependencia runtime opcional. El METADATA del wheel confirma Provides-Extra fast **sin** un Requires-Dist de Cython asociado. El build aislado ya solicita Cython de todas formas.

`setup.py:195` captura ImportError, no errores de compilación; README anuncia fallback ante fallo de compilación. El escape real es `TACHYON_SKIP_CYTHON=1`.

Wheel local construido con ese escape: `tachyon_api-1.3.1-cp313-cp313-macosx_27_0_arm64.whl`, **sin ningún .so**. Se marca como específico de intérprete/plataforma aunque el contenido Tachyon sea Python.

**Propuesta:** simplificar/documentar el contrato wheels/sdist/fallback, corregir metadata y comprobar artefactos instalados fuera del checkout. No prometer fallback automático si no se implementa y prueba.

### D07 · CI y coverage dejan huecos importantes

`.github/workflows/ci.yml` prueba solo Python 3.10; las otras plataformas/intérpretes de wheels reciben import smoke tests. El sdist se comprueba contando archivos, sin reconstruirlo. `.coveragerc` excluye módulos centrales incluso para el fallback Python.

Los 359 tests y el chequeo estructural pasan en ambos modos mientras las reproducciones de Unicode y headers difieren. La paridad de nombres no es paridad de comportamiento. Los 17 F401 de Ruff incluyen reexports internos usados por el servidor: no son 17 pruebas de código muerto.

**Propuesta:** contratos compartidos ejecutados en ambos motores; mínimo y máximo Python realmente soportado; smoke conductual del wheel instalado; rebuild del sdist; cobertura del fallback sin omitir módulos centrales.

Una exploración con Python 3.14.5 y otra resolución de dependencias dio 23 failures. No se atribuyen todos a una causa ni se comparan directamente con 3.13. La metadata permite Python >=3.10,<4; el soporte de 3.14 necesita una validación controlada antes de prometerlo.

### D08 · El cliente async y la documentación tienen deuda menor

`testing.py:41` y `:78` duplican configuración de HTTPX y no gestionan lifespan. Importar testing requiere HTTPX, que solo figura en dev. Unificar implementación interna, documentar lifespan e indicar la instalación de dependencias de testing.

CLAUDE.md anuncia un ROADMAP.md inexistente y explica que Pydantic v2 es Python: su motor de validación es nativo, por lo que esa justificación de performance debe retirarse. Los factores históricos y los conteos de tests también están desactualizados. Tratar documentación como contratos verificables, no como registro de intenciones.

## Qué conservar, simplificar y considerar eliminar

No se estableció que un subsistema entero sea código muerto. “Se puede sacar del producto” y “nadie lo usa” son afirmaciones diferentes. Las siguientes son decisiones propuestas, sin eliminaciones aplicadas.

| Elemento | Decisión propuesta | Justificación y límite |
|---|---|---|
| Compilación de metadatos por endpoint | Conservar | Mueve introspección al registro; corregir binding/tipos/cache |
| msgspec Struct y decoders | Conservar | Coherente con el objetivo; reducir la reconstrucción manual de su sistema de tipos |
| Starlette para WebSocket/lifespan | Conservar | Evita mantener protocolos propios; corregir la integración |
| Trie | Conservar condicionado a contratos | Debe resolver Unicode, nombres y prioridad antes de microoptimizar |
| Fast path sin Request | Conservar si es semánticamente equivalente | Tests compartidos con el camino general, incluidos errores y middleware |
| Writer HTTP experimental + wire helpers | Candidato principal a retirar del core estable | Rompe middleware/HEAD/headers; hace falta migración del flag y API server.run |
| Cache global `_COMPILED` | Quitar o volver local a la app/ruta | Registro poco frecuente; retención innecesaria y key incorrecta |
| Singleton Response de 500 | Quitar objeto compartido | Conservar bytes pre-renderizados; el objeto mutable es el problema |
| Tablas de 65.536 longitudes | Reducir drásticamente o retirar | 14,8 MiB medidos; decidir tamaño con datos |
| Preconversión mutante de dicts/Struct | Eliminar | Duplica trabajo del encoder y cambia estado del usuario |
| orjson + msgspec simultáneos | Medir antes de elegir uno | Quitar orjson cambia opciones, tipos y wire JSON; no es una eliminación segura sin contrato |
| CLI, server, multipart | Evaluar extras separados | Reduce instalación base si se cortan imports; no añadir paquetes/abstracciones innecesarios |
| Adaptadores cache Redis/Memcached | Mantener mínimos o documentar clientes del usuario | No ampliar backends sin casos de uso y semántica de serialización clara |
| Classes de una sola operación y delegadores de `app/`/DI | Revisar consolidación | Más archivos/objetos no garantizan mejor diseño; evitar un módulo monolítico como reacción |
| AI templates multi-herramienta | Reducir a fuente común, opcional | Preservar archivos del usuario; corregir consejos falsos |
| Nuevo migrate/TUI y objetivo fijo 12× | Posponer | Aumentan superficie antes de resolver los contratos actuales |

La fragmentación actual obliga a seguir fachada → instalador → factory → wrapper → processor para entender operaciones pequeñas. Propondría cuatro propietarios claros: registro/compilación; ejecución/contexto; respuesta/errores; adaptadores externos. Los helpers internos pueden ser funciones donde no guardan estado. La decisión debe validarse contra cambios reales, no por una meta de número de archivos.

### Inventario concreto de código sin efecto o redundante

- `setup.py:17`: import de Distribution sin uso en el archivo. Eliminación local de bajo riesgo.
- `cli/commands/lint.py:19`: argumento `check` de `_run_ruff` sin uso en su implementación ni llamadas internas. Quitar ese parámetro privado.
- `processing/compiler.py:48` y `.pyx:60`: `dep_is_async` se calcula y almacena pero no se consulta en el runtime del repositorio. El resolver comprueba el resultado real. Quitar el campo solo tras revisar compatibilidad del descriptor, o utilizarlo si existe un caso medido; hoy agrega estado sin decidir ejecución.
- `router.py:27`: `self.responses` se almacena y no se lee. Es una opción pública sin efecto, no una razón para borrarla silenciosamente. Implementar su contrato o deprecar/rechazarla explícitamente.
- `responses/_caches.py:26`: `_cl_tuple` solamente aparece como definición y reexport en el repositorio, sin consumidores internos. Candidato privado a quitar junto con la simplificación de caches; no demuestra ausencia de consumidores externos.
- `processing/response_processor.py:39`: el recorrido mutante de Struct dentro de dict es redundante con `_orjson_default`; tiene además el fallo observable A19.

No aplicar `ruff --fix` indiscriminadamente a los reexports de responses: varios los consume el servidor, incluido Cython, aunque el linter los marque F401.

## Secuencia propuesta hacia 1.4.0

Esto describe trabajo futuro; no autoriza ni representa implementación iniciada.

1. **Cerrar controles omitidos y estado compartido:** A01–A07, A16. Dependencias deben ejecutarse o rechazarse; errores CORS no deben fallar ni contaminar otra solicitud; body con límite acumulativo; desactivar writer inseguro; eliminar escalamiento Redis.
2. **Fijar contratos del motor:** A08–A15, A17–A21, schemas y JSON. Pruebas de comportamiento compartidas entre Python/Cython; errores de configuración visibles en startup. Decidir ejecución sync y vida útil de recursos.
3. **Medir baseline comparable:** async/sync separados, scopes equivalentes, ASGI puro, percentiles y validación de respuestas. Guardar datos crudos y presupuestos acordados antes de optimizar.
4. **Adelgazar:** cache de headers, imports server/CLI, cache del compilador, serialización redundante y delegadores que no aportan estado. Cambios pequeños con medida antes/después y revisión de compatibilidad.
5. **Cerrar DX y distribución:** docs ejecutables, CLI respetando archivos/modos, extras reales, pruebas del wheel/sdist y matriz de intérpretes/plataformas soportadas.

### Criterios de salida de la release

- Ningún P0/P1 abierto dentro del alcance público elegido; funciones excluidas deben rechazarse con claridad y tener migración documentada.
- Las reproducciones convertidas en contratos de regresión pasan en Python y Cython. Las rutas, middleware, errores y recursos tienen la misma semántica.
- La suite original y el ejemplo siguen pasando; wheel instalado y sdist reconstruido se prueban fuera del árbol fuente.
- Benchmarks equivalentes, con errores y percentiles registrados. Una mejora de nanosegundos no compensa bloquear el event loop o perder headers.
- Reducción medida del costo de importación/memoria y ninguna caché nueva sin límite.
- El README deja de sumar req/s como capacidad total y no promete un multiplicador sin evidencia comparable.
- Compatibilidad de API, flags de servidor, ejecución sync, defaults y extras definida antes de publicar 1.4.0.

## Fuentes externas consultadas mediante Context7

- Starlette `/kludex/starlette`: [thread pool](https://github.com/kludex/starlette/blob/main/docs/threadpool.md) y [concurrency.py](https://github.com/kludex/starlette/blob/main/starlette/concurrency.py).
- msgspec `/msgspec/msgspec/0.19.0`: [API](https://github.com/msgspec/msgspec/blob/0.19.0/docs/source/api.rst) y [extensión de tipos](https://github.com/msgspec/msgspec/blob/0.19.0/docs/source/extending.rst).
- Uvicorn `/kludex/uvicorn`: [comportamiento del servidor](https://github.com/kludex/uvicorn/blob/main/docs/server-behavior.md) y [protocolo h11](https://github.com/kludex/uvicorn/blob/main/uvicorn/protocols/http/h11_impl.py). Se leyó también el protocolo instalado de Uvicorn 0.35.0.
