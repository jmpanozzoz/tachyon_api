> Historical detection snapshot before the repair cycle. For current resolutions, validation evidence and remaining limits, see [published release validation](LOCAL_RELEASE.md).

## README.md

- **P1 · R01 · Parámetros anunciados que no existen.** La tabla de parámetros (`README.md:74`) anuncia `alias=` para todos los markers y escribe `Body(List[Struct])`. `Query`, `Path` y `Body` no aceptan `alias` (`tachyon_api/params.py`); Body recibe una descripción, mientras el tipo se obtiene de la anotación en `processing/compiler.py:_build_typed_descriptor`. Reproducción: `Query(..., alias='query')` levanta TypeError. Corregir la matriz de soporte y usar `items: list[Model] = Body()`; no ampliar la API solamente para sostener el texto. Evidencia compartida para los probes del reporte: [script](drift-probes-2026-11-04.py), [fallback](drift-probes-2026-11-04.json), [wheel nativo](drift-probes-2026-11-04-native.json).
- **P2 · R02 · Arquitectura retirada todavía documentada.** El diagrama nombra `ParameterPipeline` y `_InternalErrorResponse`, y promete mensajes ASGI preconstruidos con cero asignaciones por respuesta. Existen `ParameterProcessor`, una respuesta de error nueva por llamada y mensajes construidos en `responses/_json_response.py:__call__`; el singleton y los mensajes mutables compartidos fueron retirados. Actualizar el diagrama y quitar el costo cero anunciado.
- **P2 · R03 · El ejemplo no demuestra las features enumeradas.** La sección KYC anuncia bulk de entrada, uploads, DI transient y WebSocket con UUID. Los controllers actuales no contienen bulk ni File; `example/app.py` expone `/ws/notifications/{customer_id}` con str y `example/shared/` no contiene el generador transient prometido. La lista quedó asociada a una demo anterior.
- **P2 · R04 · Streaming aparece como pendiente sin distinguir soporte delegado.** La sección Upcoming enumera response streaming, pero `processing/response_processor.py` ya acepta una Response de Starlette y `processing/dispatch.py` llama su ASGI callable. Distinguir esa capacidad de una eventual API propia y documentar sus límites/pruebas; no anunciar el passthrough como inexistente.
- **P2 · R05 · Falta evidencia de publicación de la versión presentada.** El badge anuncia 1.4.0 estable y el texto habla de wheels publicados; `docs/audits/1.4.0/IMPLEMENTACION.md` registra preparación local, sin tag/publicación ni matriz alojada ejecutada. Los artefactos locales prueban builds locales, no distribución publicada. Alinear el estado de release con el hito efectivamente realizado.

## CLAUDE.md

- **P1 · C01 · La política de validar rendimiento todavía no tiene un gate automatizado.** La guía exige mediciones comparables antes/después. `.github/workflows/ci.yml` comprueba Ruff, tests y artefactos, pero no compara latencia/allocations contra una base ni impone un presupuesto de regresión. `benchmark/results/1.4.0-python.json` es una corrida final de fallback; el único antes/después retenido corresponde al trie Python, no al costo total del framework ni al motor compilado. Agregar baseline repetible y presupuestos antes de declarar un avance global de velocidad.
- **P2 · C02 · La validación prescrita incluye el ejemplo; el CI ordinario lo omite.** La guía pide `pytest tests/ example/tests/`, mientras los jobs de tests ejecutan solamente `tests/` y no instalan PyJWT del ejemplo. El resultado local de 17 tests del ejemplo no previene regresiones posteriores en CI. Incorporar ese contrato al pipeline con sus dependencias explícitas.
- **P2 · C03 · La regla de errores visibles en startup no cubre todos los defaults de DI.** `prepare_dependency` recorre Depends/injectables, pero `_callable_factory.py` entrega como valores los markers Header/Query/Form no reconocidos, en vez de prepararlos o rechazarlos. El ejemplo de DI documentado se registra y luego produce 500. Ver D03-01: falta decidir e imponer el subconjunto soportado.

## docs/README.md

- **P1 · I01 · Reintroduce un multiplicador retirado.** La comparación todavía publica `~5.6x throughput`, en contradicción con `benchmark/README.md` y la guía de migración, que explican que los benchmarks históricos comparaban semánticas diferentes. Retirar esa cifra o sustituirla por evidencia comparable nueva.
- **P2 · I02 · Versión y alcance de OpenAPI desactualizados.** Current dice 1.3.x frente a `pyproject.toml` 1.4.0. El cuadro resume OpenAPI automático sin remitir a las restricciones explícitas de 3.0.x, colisiones de nombres y schemas rechazados en `docs/17-migration-1.4.md`. Sin esa referencia se presenta una compatibilidad más amplia que la implementada.

## docs/01-getting-started.md

- **P1 · G01 · El CRUD de la guía falla al crear datos.** `docs/01-getting-started.md:152` usa `item.__dict__`, pero `tachyon_api.models.Struct` reexporta msgspec.Struct, sin ese atributo por defecto. La reproducción conserva AttributeError. Usar `msgspec.structs.asdict` o conversión equivalente y ejecutar el ejemplo en CI.
- **P2 · G02 · El siguiente paso del scaffolding apunta al directorio equivocado.** Tras `tachyon new my-api`, la guía indica `cd my-api`; `cli/commands/new.py:create_project` normaliza el nombre mediante `validate_name`, por lo que crea `my_api`. La estructura y los comandos deben usar el nombre efectivo.

## docs/02-architecture.md

- **P1 · A01 · Controller de creación sin Body.** El patrón recomendado declara `data: UserCreate` sin marker (`docs/02-architecture.md:63`). El instalador rechaza ese parámetro requerido si UserCreate no es una dependencia inyectable. Agregar Body al ejemplo y validar que el módulo generado/documentado arranque.
- **P1 · A02 · El repository accede a un atributo inexistente.** `docs/02-architecture.md:118` usa `data.__dict__` sobre UserCreate(Struct); reproduce AttributeError. Corregir la conversión y probar el flujo completo.
- **P2 · A03 · Inventario de archivos y símbolos corresponde a otra arquitectura.** Se nombran `_404.py`, `_405.py`, `_extractors/_base.py`/ExtractorResult y ParameterPipeline que no existen. El código usa `_error_static.py`, tuples de extracción y ParameterProcessor. OpenAPI concentra config/renderers en `_config.py` y `_html_renderers.py`, no en los múltiples archivos mostrados; security concentra API keys y credenciales en `_api_keys.py` y `_credentials.py`. Eliminar también `_wire.py` y el singleton de errores del árbol documental.
- **P2 · A04 · Clasificación cold/hot incorrecta.** Se clasifica todo `security/` como startup-only, aunque `HTTPBearer.__call__`, OAuth2 y API keys se ejecutan al resolver cada solicitud. `DocsRoutes.setup` es lazy en el primer scope, y las páginas HTML se renderizan cuando se solicitan. El hot path HTTP normal va de ASGIEntry al stack propio y al dispatcher; HTTPDispatcher queda en el flujo de compatibilidad Starlette. Corregir el mapa antes de usarlo para priorizar optimizaciones.

## docs/03-dependency-injection.md

- **P1 · D03-01 · Header dentro de Depends está documentado pero no implementado.** Los ejemplos `get_current_user(authorization=Header(...))`, `get_token` y el async con Header llegan a `_callable_factory.py:38`, que pasa el objeto Header como valor, sin extracción. Probe con header válido: 500. Implementar extracción común a endpoints/dependencias o rechazarla al registrar y documentar Request como alternativa explícita.
- **P1 · D03-02 · Request scope capturado por un singleton.** La promesa de que `B.a` es la misma instancia request-scoped A que recibe el endpoint no se cumple cuando B conserva el scope singleton por defecto (`docs/03-dependency-injection.md:85`). `_resolver.py:resolve_class_dependency` cachea el padre app-wide con su dependencia de la primera solicitud. Reproducción: Alice obtiene ambos contextos Alice; Bob obtiene `service_user=alice`, `request_user=bob`, `same_context=false`. Se confirmó en fallback y wheel nativo. Rechazar grafos de lifetime incompatibles o definir otra resolución; advertir que datos por usuario no deben quedar capturados por un singleton. Esto demuestra retención de contexto, no por sí solo una explotación externa de autorización.
- **P2 · D03-03 · Faltan límites del binding de dependencias.** El texto presenta factories como si compartieran todos los parámetros de endpoints; solo se reconocen Request/WebSocket tipados, Depends, clases registradas y defaults Python. Especificar los tipos admitidos, el rechazo de generator dependencies y cómo se validan scopes inválidos, para evitar configuraciones aceptadas silenciosamente.

## docs/04-parameters.md

- **P1 · P04-01 · Constructor Path incorrecto.** `Path(..., description='The item ID')` pasa dos valores para description (`params.py:Path.__init__`). Reproduce TypeError antes del registro. El ejemplo debe usar `Path(description=...)`.
- **P1 · P04-02 · Múltiples uploads no están implementados.** El ejemplo `/gallery` declara `images: list[UploadFile] = File(...)`, pero `_extractors/file.py:19` usa un único `form_data[name]` y no el descriptor de lista/getlist. Dos archivos terminan en un UploadFile individual y la comprensión devuelve 500. El OpenAPI también anuncia un string binary en vez de un array. Implementar el contrato entero o rechazarlo en startup hasta soportarlo.
- **P2 · P04-03 · Falta documentar el límite de listas query.** `_extractors/query_list.py` impone 1.000 elementos, incluidos los expandidos desde CSV; la guía no menciona ese límite ni su 422. Además, el split/extend ocurre antes del chequeo: el límite de cantidad no demuestra por sí solo trabajo o memoria acotados durante expansión. Documentar y comprobar entradas grandes.

## docs/05-validation.md

- **P1 · V01 · response_model no siempre valida una instancia Struct.** La guía promete validar respuestas; `response_processor.py:25` omite convert cuando el payload ya tiene exactamente el tipo declarado. msgspec no valida tipos en su constructor normal. Reproducción: `Mutable(value='wrong')` con campo int y `response_model=Mutable` responde 200 con string, en ambos motores. Definir si la API revalida o confía en modelos construidos; el contrato actual necesita esa salvedad o una corrección.
- **P2 · V02 · Struct no es inmutable por defecto.** `docs/05-validation.md:26` lo afirma, pero `models.py` reexporta Struct sin `frozen=True`; la reproducción cambia value de 1 a 2. Corregir especialmente las recomendaciones de compartir/cachear modelos.
- **P2 · V03 · Se ocultan mecanismos de validación admitidos.** La tabla reduce validators a lógica manual en servicios. msgspec 0.19 soporta `__post_init__` y Meta/Annotated; el decoder creado por el compilador los utiliza. Distinguir invariantes del modelo y validación de negocio. Documentación contrastada vía Context7: https://github.com/msgspec/msgspec/blob/0.19.0/docs/source/structs.rst .

## docs/06-security.md

- **P2 · S01 · OAuth2 no se conecta con el documento OpenAPI.** `OAuth2PasswordBearer` conserva tokenUrl y su fuente declara que lo expone para documentación, pero `_route_builder.py` omite Depends sin generar `components.securitySchemes` ni `operation.security`. El probe de una ruta OAuth2 obtiene ambos ausentes. Documentar el alcance como extracción de credenciales sin integración de UI o generar esos campos. Esto no significa que la extracción del token no funcione ni que valide JWT automáticamente.

## docs/07-caching.md

- **P2 · K01 · Las claves no incluyen identidad real de la función.** El texto dice function identity; `_default_key_builder` usa módulo/qualname y repr de argumentos. Dos closures distintas con el mismo qualname y argumentos colisionan sobre un mismo backend: funciones que retornan a y b devuelven a y a. Definir namespace/identidad apropiado o advertir explícitamente esa colisión y exigir key_builder cuando se compartan caches entre factories/apps.
- **P2 · K02 · Falla de get no tiene la política de errores anunciada de forma genérica.** La guía dice que las fallas se registran; los wrappers llaman `be.get` fuera de try y `RedisCacheBackend.get` no captura errores. Una falla de lectura propaga y puede convertir el endpoint en 500. Acotar la afirmación a las operaciones cubiertas o decidir una política explícita para cache no disponible.

## docs/08-lifecycle.md

- **P1 · L01 · Endpoint ML omite marker de entrada.** `def predict(data: InputData)` no tiene Body, path ni Depends. Si InputData es el DTO de entrada del ejemplo, `_route_installer.py` lo rechaza al registrar. El patrón recomendado necesita Body; no basta con resolver los placeholders del driver/modelo.

## docs/09-background-tasks.md

- **P1 · B01 · El ejemplo opcional no agrega tareas.** `if background_tasks:` evalúa False cuando la colección está vacía (`background.py:__bool__`); por eso `log_access` nunca se encola. Reproducido en ambos motores. Usar `is not None` para comprobar inyección.
- **P1 · B02 · Dos ejemplos no arrancan con el binding actual.** reset_password declara email requerido sin Query/Body/Form; import_data declara UploadFile sin File. Ambos quedan sin binding y el registro falla. Corregir los markers y ejecutar los ejemplos.
- **P2 · B03 · El logging no requiere el wrapper presentado como solución.** `BackgroundTasks.run_tasks` ya usa logger.exception y continúa con la siguiente tarea. Actualizar la sección de errores para describir el logging incorporado y reservar wrappers para políticas de aplicación.

## docs/10-websockets.md

- **P1 · W01 · La dependencia de autenticación mostrada no recibe WebSocket.** `get_optional_user(websocket)` no tiene anotación; CallableFactory solo inyecta el socket por tipo WebSocket/Request, mientras el shortcut por nombre aplica al endpoint, no a sus factories. El probe falla con TypeError antes de accept. Anotar el factory o ampliar la regla explícitamente.
- **P1 · W02 · date/datetime anunciados no se convierten desde texto.** La lista de tipos afirma ese soporte, pero `TypeConverter._convert_bare` llama `base_type(value_str)`, que no parsea ISO para date/datetime. Un date ISO válido devuelve error de conversión; en HTTP se midió 404 y en WebSocket el mismo converter lleva a 1008. Implementar parsing definido o retirar esos tipos de la lista.
- **P2 · W03 · Falta hacer visible el lifetime por conexión.** Se anuncian las mismas reglas de HTTP y tres scopes, pero request significa una instancia por conexión WebSocket, no por mensaje. El comportamiento está solo en la migración; incorporar esa diferencia junto a los ejemplos de sesiones/autorización prolongadas.

## docs/11-testing.md

No drift detected.

## docs/12-cli.md

- **P1 · T01 · La configuración Ruff propuesta no corresponde al archivo nombrado.** Se titula ruff.toml pero utiliza tablas `[tool.ruff]`. Ruff 0.14.9 rechaza ese archivo con unknown field tool; ese anidamiento corresponde a pyproject.toml. Alinear nombre y formato.
- **P2 · T02 · Workers de producción anunciados distintos.** La tabla dice que --prod usa cuatro workers si no se indican; `run_server` conserva el valor por defecto 1. La comprobación con uvicorn.run simulado confirma workers=1. Cambiar implementación o contrato; también corregir el help de cli/main.py que sigue diciendo workers=4.
- **P2 · T03 · Flag legado todavía anuncia transporte retirado.** Los ejemplos, tabla y help de `--tachyon-server` prometen direct socket writes/F12b. La implementación usa el modo de compatibilidad Uvicorn h11, como sí explica docs/16 y docs/17. Corregir el mensaje principal y el help, no reintroducir el writer.
- **P2 · T04 · Pasos del scaffolding vuelven a usar el nombre anterior.** Aunque el texto menciona normalización, el árbol y `cd my-api` no usan my_api, que es el directorio generado.
- **P2 · T05 · La salida principal de validate sigue siendo más fuerte que el contrato.** El ejemplo anuncia Schema is valid; el código y las notas al final solo garantizan tipos/campos básicos. Unificar el texto principal con la limitación, para que el usuario no tome ese comando como validación de especificación.

## docs/13-request-lifecycle.md

- **P1 · Q01 · Orden de BackgroundTasks contradice runtime y guía específica.** El diagrama y la sección 7 las colocan antes de serializar/enviar. El runtime construye/transmite la respuesta y luego ejecuta las tareas en `_BackgroundResponse.__call__`. Corregir el orden y añadir el cierre de recursos posterior.
- **P2 · Q02 · Parámetros no se extraen agrupados por tipo.** La guía afirma Path→Query→Header→Cookie→Form/File y después DI. `ParameterProcessor.process_parameters` recorre descriptors en orden de firma; los guards de ruta se ejecutan antes. La introspección es de registro, no una fase repetida de request.
- **P2 · Q03 · Sync no se ejecuta inline.** El pseudocódigo llama handler directamente; `ResponseProcessor.call_endpoint` usa run_in_threadpool para funciones síncronas. Documentar scheduling y contención para interpretar p99.
- **P2 · Q04 · Límite y asignaciones de respuesta obsoletos.** Indica default de body 10 MB frente a 2 MiB, y mensajes ASGI preconstruidos frente a contenedores por envío. `_add_route` tampoco existe: la instalación corre por RouteInstaller.install. Actualizar símbolos y costos.
- **P2 · Q05 · O(k) incondicional y deltas históricos no respaldados por el matcher actual.** El trie ahora puede explorar alternativas ante prefijos ambiguos; el costo depende de las ramas exploradas. Las cifras de ahorro de middleware, conversión Cython y creación de respuesta no tienen un antes/después homologado para el código actual. Acotar complejidad y reemplazar esas cifras por mediciones de la revisión vigente.

## docs/14-migration-fastapi.md

- **P1 · M01 · Sanitización anunciada no se aplica al upload recibido.** La guía promete quitar directorios/null bytes de UploadFile.filename. La clase de `files.py` lo hace en su constructor, pero el parser crea `starlette.datastructures.UploadFile` y FileExtractor lo entrega sin envolver ni sanitizar. Probe con `../../sensitive.txt`: mismo filename y `isinstance(file, tachyon_api.files.UploadFile)==False`, en ambos motores. Conectar la política al camino real; no confiar en ese nombre para guardar archivos. No se escribió ningún archivo ni se demostró traversal externo.
- **P2 · M02 · Migración de modelos elimina una restricción.** El ejemplo Pydantic prohíbe campos extra; el Struct resultante no usa forbid_unknown_fields=True, por lo que cambia validación. La tabla No Field y la recomendación de mover toda validación al servicio tampoco reflejan Meta/Annotated, msgspec.field y __post_init__. Documentar diferencias semánticas, no solamente cambios de imports.
- **P2 · M03 · scope app no es igual en HTTP y WebSocket.** La sección scope app afirma que siempre es Tachyon; en WebSocket y lifespan se delega a Starlette, que establece su instancia en scope. El resolver tuvo que vincularse explícitamente por esa diferencia. Acotar la afirmación al HTTP propio.
- **P2 · M04 · Extras de build descritos con la semántica anterior.** El comentario dice agregar fast para compilar en otras plataformas; los builds aislados ya requieren Cython y un compilador, independientemente del extra. Alinear con docs/16 y explicar que instalar fast junto a un wheel no lo recompila.
- **P2 · M05 · Compatibilidad de security sobreafirmada.** Only the import changes omite que tokenUrl no se refleja en OpenAPI/securitySchemes. Incorporar el límite S01 a la checklist de migración.

## docs/15-best-practices.md

- **P1 · F01 · El ejemplo señalado como mejor no puede registrarse.** create_user(data: UserCreate, service=Depends()) sigue sin Body. El contraste enseña una organización de capas con un binding inválido.
- **P1 · F02 · El decorador cache usa un keyword inexistente.** `@cache(ttl=300)` levanta TypeError; la API usa TTL mayúsculo. La guía nueva de cache ya lo aclara, pero esta recomendación principal no se actualizó.
- **P2 · F03 · Singleton no se crea al startup.** El texto dice creates a singleton once at startup; la resolución sigue lazy en el primer uso. Además, con el nuevo offload las instancias compartidas pueden usarse desde threads distintos. Incluir lifetime y concurrencia antes de recomendarlo como optimización universal.
- **P2 · F04 · Struct no exige un intermedio Python para dicts simples.** El texto contrapone Struct directo con un paso Python que supuestamente requieren todos los dicts. `encode_json` entrega el dict a orjson directamente; el hook Python interviene en tipos no nativos, por ejemplo Struct anidado. Medir shapes equivalentes y corregir la explicación.
- **P2 · F05 · Guía de compilación y porcentajes desactualizados.** Muestra setup.py después de instalar el paquete sin requerir checkout, y promete ~20% por uvloop sin un workload/versiones. Los wheels soportados ya contienen extensiones y el extra no recompila un wheel instalado. Alinear con docs/16 y retirar porcentajes sin evidencia de esta revisión.
- **P2 · F06 · Recomendación de trabajo pesado en BackgroundTasks omite capacidad/lifetime.** El runtime ejecuta tareas dentro del proceso y las awaitea antes del cierre del request; no hay scheduler separado, persistencia ni límite propio de concurrencia. La guía de BackgroundTasks recomienda trabajos rápidos, mientras esta checklist recomienda pesados. Resolver la contradicción y medir saturación/latencia antes de usarlo como consejo de performance.

## docs/16-cython-build.md

No drift detected.

## docs/17-migration-1.4.md

- **P1 · N01 · La frase de errores de configuración en startup es más amplia que su comprobación.** Los defaults Header de las factories documentadas son aceptados y fallan en request (D03-01). Tampoco se evita que un singleton capture un request-scoped context (D03-02). Precisar el subconjunto validado hasta imponer esos contratos.
- **P2 · N02 · La guía afirma retirada general de multiplicadores históricos, pero otros documentos los conservan.** docs/README.md sigue publicando 5.6x y docs/13 contiene deltas anteriores a las correcciones. La migración no describe todavía el estado documental real.

## example/README.md

- **P1 · E01 · SECRET_KEY no se genera.** La tabla indica default generated; `example/config.py:24` usa la cadena fija `super-secret-key-change-in-production`, y from_env solo la reemplaza si existe la variable. Corregir la afirmación y decidir un fallo explícito para el modo de producción; no atribuir generación segura a este ejemplo.
- **P2 · E02 · La cobertura por endpoint se anuncia completa pero no lo es.** Every endpoint is covered no se sostiene con `example/tests/`: no hay pruebas de websocket_connect para el canal de notificaciones ni una prueba completa de su flujo con lifespan. Las fixtures síncronas tampoco entran al contexto lifespan. Enumerar lo ejercitado o agregar las pruebas.
- **P2 · E03 · Comando de instalación y raíz de ejecución ambiguos.** La guía mezcla `pip install -r requirements.txt` relativo a example con un comando `uvicorn example.app:app` que exige la raíz del repositorio. Especificar ambos directorios; README principal incluso hace cd example antes de ejecutar example.app:app.

## benchmark/README.md

No drift detected.
