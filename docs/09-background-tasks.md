# 09. Background Tasks

> Ejecutar tareas después de enviar la respuesta

## 🎯 Uso Básico

```python
from tachyon_api import Tachyon, Query, File
from tachyon_api.files import UploadFile
from tachyon_api.background import BackgroundTasks

app = Tachyon()

def send_email(to: str, subject: str):
    """Tarea que se ejecuta en background."""
    print(f"Sending email to {to}: {subject}")
    # Lógica de envío...

@app.post("/signup")
def signup(background_tasks: BackgroundTasks):
    # Crear usuario...
    user_email = "new@user.com"
    
    # Programar email para después
    background_tasks.add_task(send_email, user_email, "Welcome!")
    
    # El cuerpo se transmite antes de ejecutar el email
    return {"message": "User created"}
```

### Flujo:
1. Request llega
2. Usuario se crea
3. **Response se transmite**
4. Email se envía; el callable ASGI termina después de las tareas

---

## 🔄 Tareas Async

```python
import asyncio

async def process_upload(file_id: str):
    """Procesar archivo de forma asíncrona."""
    await asyncio.sleep(5)  # Simular procesamiento
    print(f"File {file_id} processed")

@app.post("/upload")
async def upload(background_tasks: BackgroundTasks):
    file_id = "file_123"
    
    # Tarea async
    background_tasks.add_task(process_upload, file_id)
    
    return {"file_id": file_id, "status": "processing"}
```

---

## 📦 Múltiples Tareas

```python
def log_action(action: str, user_id: str):
    print(f"[LOG] {user_id}: {action}")

def update_stats(action: str):
    print(f"[STATS] {action} +1")

def notify_admins(message: str):
    print(f"[NOTIFY] {message}")

@app.post("/orders")
def create_order(background_tasks: BackgroundTasks):
    order_id = "order_123"
    
    # Múltiples tareas en orden
    background_tasks.add_task(log_action, "order_created", "user_1")
    background_tasks.add_task(update_stats, "orders")
    background_tasks.add_task(notify_admins, f"New order: {order_id}")
    
    return {"order_id": order_id}
```

Las tareas se ejecutan en el orden agregado.

---

## 🔧 Con Argumentos

### Posicionales

```python
def task(a, b, c):
    print(a, b, c)

background_tasks.add_task(task, "arg1", "arg2", "arg3")
```

### Keyword Arguments

```python
def send_notification(user_id: str, message: str, urgent: bool = False):
    print(f"To {user_id}: {message} (urgent: {urgent})")

background_tasks.add_task(
    send_notification,
    user_id="123",
    message="Hello!",
    urgent=True
)
```

---

## ⚠️ Manejo de Errores

Las excepciones ordinarias de una tarea se registran después del envío y no cambian esa respuesta:

```python
def risky_task():
    raise ValueError("Task failed!")

def safe_task():
    print("This still runs")

@app.get("/with-error")
def endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(risky_task)  # Fallará
    background_tasks.add_task(safe_task)   # Aún se ejecuta
    
    return {"status": "ok"}  # Response: 200 OK
```

Tachyon ya registra excepciones con `logger.exception` y continúa con la siguiente tarea. Un wrapper solo es necesario para una política propia, por ejemplo métricas o reintentos:

```python
import logging

logger = logging.getLogger(__name__)

def safe_wrapper(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Background task failed: {e}")

@app.post("/safe")
def safe_endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(safe_wrapper, risky_task)
    return {"status": "ok"}
```

---

## 🏗️ Casos de Uso

### Envío de Emails

```python
@app.post("/reset-password")
def reset_password(background_tasks: BackgroundTasks, email: str = Query(...)):
    token = generate_reset_token(email)
    background_tasks.add_task(send_reset_email, email, token)
    return {"message": "Check your email"}
```

### Procesamiento de Archivos

```python
@app.post("/import")
async def import_data(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_path = save_temp_file(file)
    background_tasks.add_task(process_csv, file_path)
    return {"status": "import_started"}
```

### Webhooks

```python
@app.post("/orders/{order_id}/complete")
def complete_order(order_id: str, background_tasks: BackgroundTasks):
    order = complete_order_in_db(order_id)
    background_tasks.add_task(send_webhook, order.webhook_url, order)
    return {"order": order}
```

### Analytics

```python
@app.get("/products/{product_id}")
def get_product(product_id: str, background_tasks: BackgroundTasks):
    product = fetch_product(product_id)
    background_tasks.add_task(track_view, product_id)
    return product
```

---

## ⚡ Opcional con Default

```python
from typing import Optional

@app.get("/data")
def get_data(background_tasks: BackgroundTasks = None):
    result = {"data": "value"}
    
    if background_tasks is not None:
        background_tasks.add_task(log_access)
    
    return result
```

---

## 📋 Comparación con Celery

| Feature | BackgroundTasks | Celery |
|---------|-----------------|--------|
| Setup | Zero | Broker required |
| Distribución | Single process | Multi-worker |
| Persistencia | No | Sí |
| Retries | Manual | Built-in |
| Scheduling | No | Sí |
| Uso | Tareas simples | Tareas pesadas |

**Regla**: usar tareas breves y medir su costo. No existe un umbral garantizado de duración ni ejecución independiente del proceso; para trabajos largos, persistentes o distribuidos, usar una cola externa.

---

## 🔗 Próximos Pasos

- [WebSockets](./10-websockets.md) - Comunicación en tiempo real
- [Testing](./11-testing.md) - Testear background tasks

Las tareas se awaitean dentro del proceso después de que termina el callable de respuesta y antes de cerrar los uploads. Las tareas síncronas usan el thread pool; las async usan el event loop. Los clientes ASGI de test esperan también esa finalización. Si el envío falla o la solicitud se cancela, no se garantiza ejecutar las tareas; el cierre de recursos del request se intenta igualmente. No hay cola persistente ni límite propio de concurrencia. Medir saturación antes de delegar trabajo; los trabajos largos requieren un sistema externo.
