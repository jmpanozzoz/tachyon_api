# 13. Request Lifecycle

La firma se inspecciona y compila una vez en `RouteInstaller.install`, al
registrar la ruta. El request usa descriptores y decoders preparados.

```text
scope HTTP → ASGIEntry → middleware del usuario → TachyonDispatcher
  → trie: ruta y método
  → guards de ruta
  → ParameterProcessor: descriptores en orden de firma (incluye DI)
  → endpoint async en event loop / endpoint sync en thread pool
  → response_model y serialización, o Response ASGI del usuario
  → envío de respuesta
  → BackgroundTasks en orden
  → cierre de formularios y uploads
```

`ASGIEntry` construye el stack HTTP de forma lazy. HTTP normal usa el stack
propio; WebSocket y lifespan se delegan a Starlette. `HTTPDispatcher` participa
en el flujo de compatibilidad Starlette. Los middlewares envuelven el envío y
pueden modificar o rechazar solicitudes antes del dispatcher.

El trie prefiere coincidencias estáticas completas y explora alternativas si
una rama estática llega a un callejón sin salida. Su costo depende de los
segmentos y ramas exploradas; no se garantiza O(k) incondicional. Una ruta
inexistente produce 404 y un método no admitido para la ruta produce 405. El dispatcher calcula el path de routing con `root_path`, conserva parámetros heredados de mounts y no altera el path original usado por Request.

Los guards se resuelven antes de los parámetros del endpoint. El procesador
recorre descriptores en orden de firma, no agrupados por Path/Query/Body. La
resolución de dependencias consulta overrides y caches según scope. Endpoints,
factories y handlers de excepción síncronos se ejecutan en un thread pool;
trabajo bloqueante dentro de `async def` bloquea el event loop.

El body total admite **2 MiB por defecto**, acumulados entre chunks y compartidos
por JSON, forms, archivos y lecturas de Request. Superar el límite devuelve 422.
Un Request y su body/form cacheados se reutilizan durante la solicitud. La
validación de JSON usa msgspec; errores de entrada producen 422.

`ResponseProcessor` valida el JSON de `response_model` mediante encode/decode de msgspec y serializa con msgspec todos los resultados validados. Sin `response_model`, los Struct usan msgspec y otros valores JSON usan orjson. Un Struct construido o mutado manualmente también se
revalida cuando hay `response_model`. Una `starlette.responses.Response`,
incluyendo `StreamingResponse`, se invoca por ASGI. En streaming, el envío y los
errores del iterador pertenecen a ese flujo; un error después del inicio no debe
producir una segunda respuesta. Las tareas agregadas por Tachyon se ejecutan
cuando el callable de respuesta termina.

Los mensajes ASGI y headers mutables pertenecen a cada envío. Solo se comparten
bytes inmutables y tablas pequeñas acotadas: no hay singleton mutable de errores
ni garantía de cero asignaciones por respuesta. El cache de content-length cubre longitudes 0–1023; cuerpos mayores calculan su header al construir la respuesta.

Las rutas de documentación se instalan de forma lazy. Sus URLs locales de schema siguen `root_path`; URLs externas conservan su destino. La respuesta del schema agrega un `servers` con el prefijo del request solo cuando no se configuraron servidores explícitos, mediante una copia superficial que no muta el schema cacheado.

Después del envío, `BackgroundTasks` ejecuta las tareas en orden y registra sus
excepciones sin impedir la tarea siguiente. El request espera su finalización
antes del cierre de uploads. Si el envío falla o la solicitud se cancela, las tareas no tienen ejecución garantizada; el cierre del request se intenta en `finally`, también para errores de validación o transmisión. No es una cola persistente ni un scheduler separado.

Las excepciones del endpoint se traducen mediante los handlers registrados;
`HTTPException` conserva su status. Los errores de envío o stream no se convierten
en otra respuesta. Medir latencia y contención con workloads equivalentes; no se
atribuyen ahorros históricos a esta implementación sin un antes/después válido.

- [Background Tasks](09-background-tasks.md)
- [Migration to 1.4](17-migration-1.4.md)
- [Benchmark method](../benchmark/README.md)
