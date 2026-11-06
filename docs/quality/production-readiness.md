# Plan de preparación para producción y adopción

Fecha: 2026-11-06. Autor: Juan Manuel Panozzo Zénere.
Estado: propuesta de implementación posterior a 1.4.3; tareas pendientes.

Este plan convierte las cinco prioridades de producción en entregas verificables.
Incluye ampliar la demo existente y reorientar la CLI. No cambia la versión ni
declara ejecutadas las pruebas futuras. La versión de publicación se decide con
el contrato final: nuevas capacidades públicas como dependencias con `yield`
deben evaluarse para una versión minor; los arreglos compatibles pueden salir
antes. No se modifica el tag ni el paquete publicado de 1.4.3.

## Punto de partida comprobado

- [1.4.3 publicada](../audits/1.4.3/PUBLICATION.md): 933 tests de código y ejemplo
  por intérprete 3.10–3.13, 229 contratos por wheel original/reconstruido y 40
  controles locales. La ejecución de esa publicación fue en macOS ARM64.
- [Carga de 1.4.3](../audits/1.4.3/README.md): 60 segundos activos, unos 75 segundos
  totales; no acredita resistencia durante horas ni operación con base de datos.
- `example/` contiene una demo KYC con JWT, DI, clientes, verificaciones,
  background tasks, WebSockets y pruebas sync/async. Se amplía esta aplicación.
- Los repositorios usan diccionarios globales; autenticación guarda contraseñas
  sin hash. `get_customer` describe permisos que no comprueba y `/recent` no
  restringe el listado a administradores. Verificaciones tampoco comprueban
  propiedad en sus controladores. El WebSocket acepta sin autenticar.
- Las verificaciones dependen de tareas en el proceso, esperas y resultados
  aleatorios. El gestor de WebSockets es local al proceso. Esto no sirve como
  referencia de trabajo durable o notificaciones entre varios workers.
- `get_bindings` rechaza generadores; el cierre actual de uploads no proporciona
  por sí solo un contrato general de salida de dependencias.
- La CLI está activa y probada: `new`, `generate`/`g`, `run`, `routes`, `openapi`,
  `lint`, `version` e `install-skill`. Genera una aplicación mínima, no esta demo
  operable con PostgreSQL. OpenAPI validate comprueba estructura básica y routes
  lista HTTP; no se presentan como validación completa o inventario WebSocket.
- El usuario dispone de un servidor Linux. Distribución, arquitectura, recursos,
  acceso y coexistencia con otros servicios siguen pendientes de inventario.
  GitHub Actions no inició el último workflow por un bloqueo de facturación;
  tener jobs configurados no se considera cobertura ejecutada.

## Alcance y orden

| Frente | Entregable | Condición de cierre |
| --- | --- | --- |
| P1. Recursos por petición | Dependencias con salida y contrato de lifetime | Cierre comprobado ante éxito, error, cancelación y transmisión fallida |
| P2. Linux y operación | Suite instalada, carga y recuperación en el servidor | Evidencia reproducible de las plataformas realmente ejecutadas |
| P3. Demo de referencia y CLI | KYC persistente, segura y reproducible; CLI útil para empezar | Un checkout limpio permite instalar, migrar, probar y ejecutar el flujo completo |
| P4. Mantenimiento y compatibilidad | Políticas y matriz ejecutable | Contratos, límites de soporte y procedimientos publicados y comprobables |
| P5. Pilotos y adopción | Uso acotado real y resultados públicos reproducibles | Un piloto aceptado con observabilidad, responsable y rollback ensayado |

P2 comienza con el inventario y baseline 1.4.3 mientras se diseña P1. Las
correcciones de permisos y contraseñas de P3 pueden adelantarse; la persistencia
con DI depende de P1. La carga representativa de P2 depende de P3. P4 empieza
desde el primer cambio y P5 requiere cerrar los controles de los otros frentes.
No se espera al final para probar Linux.

## P1. Recursos por petición

1. **P1.1 — Fijar el contrato antes de escribir el resolver.** Proponer
   generadores async y sync como proveedores de `Depends`, con exactamente un
   `yield`. Una adquisición por dependencia cacheada y por petición; salida en
   orden inverso; aislamiento entre peticiones y aplicaciones; salida parcial si
   falla una dependencia posterior. Conservar las restricciones de captura de
   singletons y los overrides. No ampliar implícitamente el lifetime a WebSocket:
   documentar inicialmente el caso HTTP y rechazar explícitamente el caso no
   soportado. Revisar decoradores, partials y callables con `__call__`.
2. **P1.2 — Integrar propiedad y errores.** Añadir la pila de salida al contexto
   de petición solo cuando haga falta. Mantener los recursos durante la
   transmisión, incluyendo streaming, y cerrarlos aunque falle `send`, se
   desconecte el cliente o se cancele el handler. Mantener el cierre de uploads
   después del trabajo que los necesita. El contrato actual de background tasks
   sigue terminando antes de la limpieza; la demo nueva pasa identificadores y
   abre sus propios recursos para no depender de ese orden.
3. **P1.3 — Separar transacción y cierre.** La demo confirma la transacción antes
   de devolver una respuesta de éxito. La salida de la dependencia libera la
   sesión y revierte cualquier transacción pendiente; no confirma escrituras
   después de mandar un 2xx. Un fallo posterior a las cabeceras se registra y
   propaga sin intentar una segunda respuesta. La cancelación vuelve a propagarse
   tras una limpieza acotada; ninguna protección de limpieza puede colgar el
   proceso indefinidamente.
4. **P1.4 — Resolver sync sin promesas de afinidad falsas.** Evitar trabajo
   bloqueante en el event loop. Probar entrada/salida sync y agotamiento del pool
   de threads. No prometer el mismo thread para entrada, uso y salida: los recursos
   con afinidad de thread requieren una estrategia comprobada o un error explícito
   y una limitación documentada. La demo principal usa sesiones async por tarea.
5. **P1.5 — Probar el contrato.** Éxito, error antes/dentro/después de `yield`,
   cero o varios yields, anidación, overrides, caché, peticiones concurrentes,
   cierre fallido, validación de respuesta, streaming, background tasks,
   disconnect y cancelación. Verificar orden y número de cierres y conservación
   del error original, no solo el status HTTP. Medir rutas sin DI para evitar
   añadir estado o trabajo a su camino rápido.

Archivos previstos: `tachyon_api/processing/dependencies/_sig_cache.py`,
`_callable_factory.py`, `_resolver.py`, `_scope_cache.py`; `tachyon_api/processing/scope.py`;
`tachyon_api/app/_handler_factory.py`, `_http_dispatch.py` y
`tachyon_api/processing/response_processor.py` para el orden real de ejecución;
`tests/test_depends_callable.py`, `tests/test_continuous_di.py`,
`tests/test_server_integration.py` y nuevo `tests/test_dependency_cleanup.py`.
Actualizar `docs/03-dependency-injection.md`, `08-lifecycle.md`,
`09-background-tasks.md`, `13-request-lifecycle.md`, `14-migration-fastapi.md` y
`CHANGELOG.md` con el contrato finalmente elegido. Los nombres nuevos son
propuestos; el PR de implementación debe reconciliarlos con el código final.

**Aceptación:** matriz anterior aprobada, suite completa e instalada en los
intérpretes soportados, sin sesión compartida entre tareas concurrentes, sin
limpieza duplicada ni respuesta duplicada. Comparación repetida del camino sin DI
contra 1.4.3; cualquier regresión sostenida superior al 5% requiere investigación
y decisión explícita antes de cerrar, no se compensa con otro escenario.

## P2. Linux y operación en el servidor disponible

1. **P2.1 — Inventario sin carga.** Registrar distribución/kernel, CPU y
   arquitectura, RAM, disco, contenedores disponibles, límites de procesos y
   archivos, runtimes instalables, servicios existentes y espacio libre.
   Identificar un usuario y directorio de pruebas, puertos y topes de CPU/RAM/disco.
   No inferir acceso de un alias ni instalar paquetes o reiniciar servicios
   compartidos durante la planificación. El ensayo debe limitarse al entorno de
   pruebas acordado cuando se disponga de acceso.
2. **P2.2 — Baseline instalada.** Descargar 1.4.3, verificar sus hashes contra
   PyPI y ejecutar contratos fuera del checkout. Ejecutar la suite fuente en
   3.10–3.13 y los controles de wheel/sdist; si falta un intérprete, registrar ese
   hueco en vez de declararlo probado. Repetir con la candidata de P1/P3. Una
   máquina x86-64 no acredita ARM64 ni a la inversa; tampoco acredita Windows.
3. **P2.3 — Despliegue reproducible.** Contenedores de API, PostgreSQL, Redis y
   worker de la demo; migraciones como paso único previo al arranque, no por
   worker HTTP. Configurar límites de pools, timeouts, logs y almacenamiento.
   Probar un worker y luego varios; no elegir su cantidad por un supuesto de CPU.
4. **P2.4 — Escalera de carga.** Smoke de 10 minutos; ciclo representativo de
   2 horas; carga de 8 horas con fases de reposo; ensayo de 24 horas previo a
   promocionar un piloto importante. Se avanza solo tras revisar la etapa anterior.
   Mezclar login, lecturas, escrituras, validaciones inválidas, trabajos y
   notificaciones con proporciones registradas. Separar pruebas hostiles y de
   saturación de la medición normal. Usar generador externo cuando sea posible;
   si comparte host, registrar CPU y límites del cliente y no inferir capacidad.
5. **P2.5 — Fallos y recuperación.** Reinicio de API/worker, caída y regreso de
   Redis/DB, timeout del proveedor, pérdida del cliente y despliegue con SIGTERM.
   Comprobar recuperación del pool, persistencia, idempotencia, reanudación de
   jobs y reconciliación de notificaciones. Ensayar backup/restauración y rollback
   de aplicación contra un esquema compatible; downgrade de esquema no se
   considera rollback seguro por defecto.
6. **P2.6 — Informe verificable.** Reutilizar `scripts/local_release.py`,
   `scripts/test_installed_wheel.py`, `benchmark/run_endurance.py` y
   `benchmark/run_benchmark.py`; extenderlos solo si falta un contrato. Añadir un
   driver de negocio para la demo y un colector Linux. Conservar commit, hashes,
   versiones, configuración, mezcla de tráfico, errores esperados/inesperados,
   p50/p95/p99, RSS por proceso y total, FDs, pools, event-loop lag, CPU, colas y
   condiciones de recuperación. Los samples limitados deben explicar cómo se
   estimaron los percentiles y conservar los contadores totales.

Presupuestos iniciales de aceptación, propuestos para calibrar con el baseline:
cero pérdidas o duplicados de negocio, cero 5xx inesperados en carga normal,
conexiones/FDs devueltos al rango de reposo y colas dentro de su plazo configurado.
Tras warmup, investigar todo crecimiento de RSS en reposo mayor al 10% o 32 MiB
(lo que sea mayor), sin aumento de datos o caché que lo explique; superar ese
umbral bloquea el cierre hasta explicar y repetir. Comparar ventanas equivalentes
del inicio/final para detectar crecimiento sostenido, incluso por debajo del
umbral. No declarar ausencia de leaks a partir de RSS estable. Fijar el SLO
absoluto de latencia del servicio con el baseline y su carga objetivo; no inventar
un SLA independiente del hardware y la DB. Saturación e inyección de fallos tienen
sus propios errores esperados, recuperación y plazos documentados.

Archivos nuevos propuestos: `scripts/linux_validation.py`,
`benchmark/run_reference_workload.py`, `docs/quality/linux-validation.md` y un
directorio de resultados fechado bajo `docs/quality/evidence/`. Reutilizar los
workflows existentes como contratos; un servidor de pruebas no se convierte en
runner de PRs no confiables. Resolver el bloqueo de facturación de Actions sigue
siendo una tarea de cuenta independiente.

## P3. Mejorar la demo existente y hacer útil la CLI

### P3.A — Demo KYC como aplicación de referencia

Conservar `example/`, los módulos de autenticación/clientes/verificación y los
DTOs msgspec. Mantener el proveedor KYC simulado, pero determinista y configurable:
la referencia demuestra ingeniería backend, no verificación de identidad real.
Usar datos sintéticos. Evitar un segundo ejemplo completo en otro repositorio.

- **P3.1 — Aislamiento de aplicación.** Introducir una factory y settings
  explícitos. Pools y clientes en lifespan; sesión por petición/tarea; servicios
  que capturan sesiones pasan a scope request. Eliminar stores globales y limpiar
  fixtures que dependen de caches privadas del framework.
- **P3.2 — Persistencia.** Propuesta: PostgreSQL, SQLAlchemy async 2.x y Alembic,
  solo como dependencias de la demo. Modelos de usuarios, clientes, verificaciones,
  checks y trabajos/eventos pendientes. Constraints de unicidad/propiedad e
  índices, paginación acotada y transacciones explícitas. Probar migración de DB
  vacía y de versión anterior con datos; revisar toda migración autogenerada.
  No simular PostgreSQL con SQLite en los tests de integración.
- **P3.3 — Autenticación y permisos.** Hash de contraseñas con Argon2id mediante
  biblioteca mantenida; ejecutar hashing bloqueante fuera del event loop y
  limitar su concurrencia. Claims JWT obligatorios y verificables, expiración,
  usuario activo consultado en DB y roles/propiedad en cada operación. Restringir
  `/recent` a admin; comprobar propiedad al leer/iniciar verificaciones y antes
  de aceptar WebSockets. Para navegador, ticket WebSocket de corta vida y un uso,
  emitido por HTTP autenticado; no poner JWT duradero en la URL. Probar origen,
  expiración y replay del ticket. Limitar intentos de login y usar respuestas que
  no revelen si existe una cuenta. Seeds y credenciales demo solo bajo opt-in
  explícito de desarrollo/test; secretos y configuración inseguros fallan al arrancar.
- **P3.4 — Trabajo durable y varios workers.** Guardar la verificación y su job
  en una transacción; procesar con un worker separado usando una cola en PostgreSQL
  con reclamación atómica, lease, reintentos acotados e idempotencia. Evitar añadir
  un broker/SDK de jobs al núcleo. El worker abre sus sesiones, recibe IDs y
  sobrevive a reinicios sin perder trabajo. Publicar notificaciones entre procesos
  vía Redis; el estado durable sigue en DB y el cliente reconcilia al reconectar.
  Redis Pub/Sub no se presenta como entrega durable o exactamente una vez.
- **P3.5 — Caché y degradación.** Usar Redis con TTL, namespace, invalidación tras
  commit y separación por permisos. Su caída permite leer desde DB con timeout
  acotado; no cambia autorización ni falsea la disponibilidad del worker.
- **P3.6 — Contratos de API.** Errores predecibles, validación de entrada/salida,
  límites de tamaño, paginación, cookies/headers según los flujos usados,
  idempotencia para iniciar verificaciones y streaming de exportación acotada.
  Añadir una carga de archivo sintético limitada si valida un contrato relevante;
  no almacenar documentos personales ni inventar un producto de almacenamiento.
- **P3.7 — Operación visible.** Liveness independiente de DB; readiness con
  timeout para dependencias necesarias, diferenciando degradación por caché.
  Logs estructurados con correlación y redacción, métricas de latencia/errores,
  pools y jobs. Sin tokens, contraseñas, payloads KYC ni IDs de usuario como labels.
  Probar cabeceras de correlación en errores, no solo en respuestas exitosas.
- **P3.8 — Reproducción.** Dockerfile, Compose, `.env.example`, migraciones,
  seed explícito, comandos de prueba y guía desde cero. Fijar versiones probadas
  de herramientas/servicios y registrar resolución; no depender de `latest`.
  Separar tests rápidos, integración PostgreSQL/Redis y aceptación por red real.

Archivos existentes a revisar: `example/app.py`, `config.py`, `requirements.txt`,
`README.md`; controladores, servicios, repositorios y DTOs de los tres módulos;
`shared/dependencies.py`, `request_context.py`, `exceptions.py`,
`websocket_manager.py`; todos los fixtures y tests del ejemplo. Archivos nuevos
propuestos: `example/shared/database.py`, `models.py`, `cache.py`,
`observability.py`, `example/modules/auth/auth_repository.py`,
`example/modules/verification/jobs.py`, `example/worker.py`, `example/seed.py`,
`example/alembic.ini`, `example/migrations/`, `example/Dockerfile`,
`example/compose.yaml`, `example/.env.example` y tests de integración/aceptación.
Actualizar las guías de seguridad, caching, testing y buenas prácticas según las
integraciones que realmente funcionen; no afirmar cobertura antes de ejecutarla.

### P3.B — CLI: conservar, enfocar y comprobar lo que genera

La CLI conserva valor si reduce el tiempo desde instalar hasta tener una API
correcta y diagnosticable. No requiere una reescritura completa ni una TUI.

| Capacidad | Plan | Prueba de aceptación |
| --- | --- | --- |
| `new`, `generate`/`g` | Conservar comandos y defaults; proponer perfiles explícitos `minimal` y `postgres` | Proyecto generado fuera del repo instala, migra cuando corresponde, ejecuta tests y responde por HTTP |
| `doctor` nuevo | Python/dependencias, target ASGI, configuración y extras; texto y JSON, códigos de salida estables | Diagnósticos accionables y secretos redactados; sin cambios de archivos, arranque de servidor ni conexiones por defecto |
| `routes` | Conservar salida actual; añadir JSON e inventario explícito HTTP/WS | Coincide con la aplicación registrada, declara imports con efectos y no ejecuta lifespan |
| `openapi` | Conservar export; mantener validación básica etiquetada y proponer validación completa opcional | Un esquema inválido produce salida no cero; si falta el validador, explicar instalación sin afirmar validación completa |
| `run` | Mantener wrapper Uvicorn y flags actuales; aclarar modo dev/producción | Args y errores comprobados; `--prod` no se vende como orquestación o configuración productiva completa |
| `lint` e `install-skill` | Mantener compatibilidad y correcciones focalizadas | Modo lectura no modifica archivos; contenido del usuario preservado; contexto actualizado al API publicado |

- **P3.9 — Medir el recorrido existente.** Ejecutar `new → instalar → generate →
  registrar router → tests → run → HTTP → exportar OpenAPI` desde un directorio
  limpio. Registrar pasos manuales, problemas y tiempo; no basar la decisión en
  el número de comandos. Revisar nombres plurales, archivos ya existentes,
  generación parcial y paths antes de ampliar opciones.
- **P3.10 — Compartir contratos con la demo.** El perfil PostgreSQL es un starter
  pequeño que usa los patrones de lifecycle/configuración/persistencia probados
  por la demo; no copia todo KYC. Usar una sola fuente de plantillas para generar
  ambos artefactos comunes cuando sea viable; donde la demo necesite código
  específico, comprobar contratos equivalentes con tests y fixtures compartidos.
  No mantener dos árboles genéricos de autenticación que diverjan silenciosamente.
- **P3.11 — Diagnóstico seguro y automatizable.** `doctor` ofrece checks de
  conectividad solo por opt-in, con timeout; no importa la app por defecto si
  puede ejecutar código arbitrario. Diferenciar estático, import y red en la ayuda.
  No mostrar credenciales en URLs o errores. Mantener `--help` y `version` utilizables
  sin DB/Redis y evitar importar herramientas opcionales en runtime HTTP.
- **P3.12 — No duplicar otras herramientas.** Las migraciones siguen siendo de
  Alembic y la operación de Compose/servicio sigue en el runbook. Ruff sigue siendo
  Ruff. La CLI puede documentar o invocar una herramienta explícitamente, pero no
  añade otro motor de migraciones, gestor de paquetes o despliegue remoto.
  No mover Typer fuera de la instalación por defecto como cambio patch incidental.

Archivos: `tachyon_api/cli/main.py`, `utils.py`, comandos `new.py`, `generate.py`,
`routes.py`, `openapi.py`, `run.py`, plantillas `project.py`, `service.py`,
`ai_skill.py`, nuevo `commands/doctor.py`; `tests/test_cli.py`,
`tests/test_audit_dx.py`, nuevos tests de proyectos generados;
`docs/12-cli.md`, `docs/01-getting-started.md` y requisitos de desarrollo.
La sintaxis de opciones nuevas es propuesta, no documentación de comandos ya
disponibles. No eliminar ni renombrar comandos existentes sin migración.

### Matriz mínima de aceptación de la demo y CLI

| Área | Casos obligatorios |
| --- | --- |
| Identidad | Registro/login, hash, token inválido/expirado, claims faltantes, usuario desactivado, rate limit |
| Permisos | Usuario A no lee/modifica/inicia ni recibe eventos de B; admin explícito; listados filtrados |
| Persistencia | Reinicio conserva datos, constraints bajo concurrencia, commit fallido no produce éxito, rollback y pool recuperado |
| Jobs | Reinicio antes/después de commit, reclamación concurrente, retry, lease vencida y efecto idempotente |
| WebSocket | Auth y origen antes de aceptar, ticket expirado/reusado, aislamiento, dos workers, desconexión y reconciliación |
| Cache | Hit/miss, TTL, invalidación post-commit, caída de Redis y ausencia de datos cruzados |
| Transporte | HTTP real, errores de validación, cuerpo limitado, cancelación, streaming y cierre de recursos |
| Contrato | Esquema OpenAPI válido para el subconjunto anunciado y coherente con la API, errores y modelos reales |
| Despliegue | DB vacía y upgrade, arranque fallido, health/readiness, SIGTERM, restore y rollback compatible |
| CLI | Instalación desde wheel, proyecto generado ejecutable, paths con espacios, colisiones sin sobrescritura, ayuda y JSON estables |

La meta es cubrir el 100% de las operaciones públicas de la demo con éxito y
fallo relevantes, usando una lista explícita de operaciones y escenarios. Añadir
branch coverage como indicador y revisar huecos en auth, transacciones y cleanup;
un porcentaje global alto no sustituye los contratos. Los tests del framework,
los unitarios de la demo, las integraciones y la carga son evidencias distintas.

## P4. Mantenimiento, compatibilidad y soporte

1. **P4.1 — Compatibilidad comprobada.** Mantener Python 3.10–3.13 y probar
   combinaciones mínimas/resueltas dentro de los rangos declarados. Incluir las
   integraciones con hooks privados de Starlette: forms, errores, routing,
   lifespan y WebSocket. Verificar instalación desde wheel/sdist y OpenAPI.
   Probar por separado los extras; DB/Redis/telemetría de la demo no pasan al core.
2. **P4.2 — Políticas honestas.** Documentar versiones soportadas, deprecación,
   migración, reporte privado de vulnerabilidades y responsable de triage. No
   prometer respuesta 24/7 ni SLA sin capacidad de cumplirlos. Distinguir soporte
   del proyecto, soporte comunitario y plataformas no verificadas.
3. **P4.3 — Operación y cambios.** Runbook de errores, pools, picos de latencia,
   cancelaciones, jobs atascados, backup/restore y rollback. Cambios públicos con
   ejemplos de migración y evidencia de regresión. Auditar dependencias y conservar
   fechas/resultados; no confundir ausencia de advisories con seguridad garantizada.
4. **P4.4 — Publicación y docs.** Reutilizar los controles locales cuando Actions
   no esté disponible. Actualizar el índice activo desde evidencia de la versión
   real; conservar históricos. Landing consume únicamente métricas de versión y
   hash coincidentes. No ampliar promesas de plataforma antes de tener resultados.

Archivos propuestos: `SECURITY.md`, `CONTRIBUTING.md`,
`docs/quality/support-policy.md`, `dependency-compatibility.md`,
`operations-runbook.md`; `.github/workflows/ci.yml`, `build-wheels.yml`,
`scripts/test-requirements.txt`, `scripts/local_release.py`, tests de contratos,
`docs/README.md` y guías afectadas. Documentar GPL-3.0-or-later consistentemente;
este plan no cambia licencia ni promete una revisión legal.

**Aceptación:** matriz con resultados y huecos reales, guía para reportar un
problema/reproducirlo, responsables y límites públicos, release repetible y
simulación documentada de incidente/restauración/rollback.

## P5. Pilotos y adopción

1. **P5.1 — Elegir un primer servicio acotado.** Tráfico y dependencias conocidos,
   equipo responsable, observabilidad, criterio de éxito y retorno a la versión
   anterior. No usar el primer piloto para un sistema crítico sin alternativa.
   El servidor de pruebas y la demo no cuentan como un usuario de producción.
2. **P5.2 — Medir valor de adopción.** Tiempo hasta primer endpoint y despliegue,
   dificultades del desarrollador, documentación faltante, incidentes, latencias,
   consumo y cambios requeridos. Proponer una observación inicial de dos semanas;
   ampliarla si no cubre tráfico o eventos representativos. No fijar una cuota de
   tráfico arbitraria como prueba de madurez.
3. **P5.3 — Comparar cargas equivalentes.** Conservar los escenarios existentes
   contra FastAPI y añadir una aplicación equivalente con DB, mismos índices,
   validación, auth, pools y payloads cuando el piloto lo justifique. Publicar
   limitaciones y datos reproducibles; no sumar req/s de escenarios ni prometer
   un multiplicador global. La mejora del framework puede quedar diluida por I/O.
4. **P5.4 — Publicar la evidencia útil.** Guía de elección, diferencias frente a
   FastAPI, tutorial que ejecuta la CLI real y caso del piloto con permiso del
   participante. Actualizar README y landing con resultados comprobados, sin
   nombres de clientes o logos sin autorización.

Entregables: plantilla de piloto, registro de hallazgos y caso reproducible bajo
`docs/adoption/`; cambios de tutoriales/benchmark en este repositorio; contenido
de `../tachyonapi-web/` solo al disponer de evidencia nueva.

**Aceptación:** piloto con criterios acordados cumplidos, incidentes resueltos o
limitaciones explícitas, rollback ensayado y documentación que otra persona pueda
seguir desde cero. Los proyectos de terceros requieren participación de sus
responsables; no se inventan ni se consideran cerrados con una publicación web.

## Entregas revisables y dependencias

| Entrega | Tareas | Evidencia para continuar |
| --- | --- | --- |
| E0. Baseline y contratos | P2.1/P2.2, P3.9, diseño P1.1, inicio P4 | Inventario Linux; recorrido CLI actual; reglas de lifetime revisadas |
| E1. Recursos HTTP | P1.2–P1.5 | Contratos de cierre, suite instalada y comparación sin DI |
| E2. Seguridad y persistencia | P3.1–P3.3, migraciones, tests | Dos usuarios aislados, datos durables y transacciones correctas |
| E3. Operación de la demo | P3.4–P3.8, P2.3, P4.3 | Jobs recuperables, dos workers, métricas y Compose reproducible |
| E4. CLI y documentación | P3.10–P3.12, P4.1/P4.2/P4.4 | Starter comprobado fuera del repo; doctor; compatibilidad y soporte |
| E5. Resistencia Linux | P2.4–P2.6 | Informes de carga por etapas y recuperación; presupuestos aceptados |
| E6. Piloto y comunicación | P5.1–P5.4 | Operación real observada y caso reproducible |

E2 puede adelantar permisos/hash antes de E1; E4 puede adelantar `doctor` mientras
se estabiliza la persistencia. Las pruebas Linux acompañan todas las entregas.
Crear PRs separados por contrato y por migración de la demo; no acumular los cinco
frentes en un solo cambio. No fijar fechas de release antes de inventariar el
servidor y completar el diseño de cleanup. Las 8/24 horas son tiempo de ejecución
de carga, no estimaciones de implementación.

## Riesgos, decisiones propuestas y pendientes

- Aumentar la demo puede volverla difícil de entender: mantener starter mínimo,
  añadir una guía progresiva y justificar cada servicio externo por un contrato.
- Mantener `yield` vivo durante streaming retiene recursos: la demo materializa
  lecturas pequeñas y usa sesiones explícitas/acotadas para exportaciones; no
  mantiene una transacción de escritura mientras envía una respuesta lenta.
- PostgreSQL como cola evita otro broker, pero exige probar leases, reintentos y
  concurrencia. Se limita al volumen de la demo/piloto y se documenta su frontera;
  no se presenta como sistema universal de trabajos.
- Un único servidor no da redundancia, segunda arquitectura ni clientes remotos
  sin contención. Describir exactamente lo medido y reservar recursos si comparte
  otros servicios. No instalar un runner abierto de GitHub en ese servidor.
- Los perfiles de CLI tienen costo de mantenimiento: comenzar con dos perfiles
  comprobados; no generar combinaciones arbitrarias de ORM, broker y autenticación.
- Pendiente del usuario: inventario/alias de acceso del servidor, si es dedicado
  o compartido, recursos utilizables y disponibilidad de un generador externo.
  El plan puede implementarse localmente hasta necesitar esos datos.
- Propuestas que se validan en los PRs: SQLAlchemy async/Alembic para la demo,
  PostgreSQL para jobs, Redis para caché/notificaciones y alcance HTTP inicial de
  `yield`. No son dependencias nuevas ya adoptadas por este documento.
- No se agregan Rust, TUI, ORM propio, proveedor KYC real, panel administrativo
  ni compatibilidad total con FastAPI para cumplir este plan.

## Fuentes y comprobación del diseño

Se contrastaron código, tests y guías existentes el 2026-11-06. Context7 se usó
para consultar documentación primaria de SQLAlchemy 2.0.55, FastAPI y Alembic.

- [SQLAlchemy: sesión por thread / AsyncSession por tarea](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks).
  Fundamenta el aislamiento de sesiones; no se comparte una sesión request en
  tareas concurrentes ni se captura en singletons.
- [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
  Fundamenta contextos explícitos de sesión, transacción y liberación del engine.
- [FastAPI: dependencias avanzadas](https://fastapi.tiangolo.com/advanced/advanced-dependencies/).
  Muestra por qué el momento de cleanup afecta streaming. Se consulta como
  antecedente, no como promesa de paridad de Tachyon.
- [Alembic: asyncio](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)
  y [limitaciones de autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).
  Sustentan el paso de migración explícito y la revisión de cada migración.
