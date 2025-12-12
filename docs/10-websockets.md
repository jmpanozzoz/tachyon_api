# 10. WebSockets

> Comunicación bidireccional en tiempo real

## 🎯 Uso Básico

```python
from tachyon_api import Tachyon

app = Tachyon()

@app.websocket("/ws")
async def websocket_endpoint(websocket):
    await websocket.accept()
    
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")
```

### Cliente JavaScript:
```javascript
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onmessage = (event) => {
    console.log("Received:", event.data);
};

ws.send("Hello!");
// Output: "Echo: Hello!"
```

---

## 📡 Operaciones Disponibles

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    # Aceptar conexión
    await websocket.accept()
    
    # Recibir
    text = await websocket.receive_text()
    data = await websocket.receive_json()
    bytes_data = await websocket.receive_bytes()
    
    # Enviar
    await websocket.send_text("Hello")
    await websocket.send_json({"message": "Hello"})
    await websocket.send_bytes(b"binary data")
    
    # Cerrar
    await websocket.close()
```

---

## 📍 Path Parameters

```python
@app.websocket("/ws/{room_id}")
async def room_endpoint(websocket, room_id: str):
    await websocket.accept()
    await websocket.send_text(f"Welcome to room: {room_id}")
    
    while True:
        message = await websocket.receive_text()
        await websocket.send_text(f"[{room_id}] {message}")
```

### Conexión:
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/lobby");
```

---

## ❓ Query Parameters

```python
@app.websocket("/ws")
async def authenticated_ws(websocket):
    await websocket.accept()
    
    # Acceder a query params
    token = websocket.query_params.get("token")
    
    if not token:
        await websocket.send_json({"error": "No token"})
        await websocket.close()
        return
    
    await websocket.send_json({"authenticated": True})
```

### Conexión:
```javascript
const ws = new WebSocket("ws://localhost:8000/ws?token=abc123");
```

---

## 🔄 Chat Room Example

```python
from tachyon_api import Tachyon
from typing import Dict, List

app = Tachyon()

# Almacenar conexiones activas
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List] = {}
    
    async def connect(self, websocket, room: str):
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = []
        self.active_connections[room].append(websocket)
    
    def disconnect(self, websocket, room: str):
        self.active_connections[room].remove(websocket)
    
    async def broadcast(self, message: str, room: str):
        for connection in self.active_connections.get(room, []):
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/chat/{room}")
async def chat(websocket, room: str):
    await manager.connect(websocket, room)
    
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"[{room}] {data}", room)
    except Exception:
        manager.disconnect(websocket, room)
```

---

## ⚠️ Manejo de Desconexión

```python
from starlette.websockets import WebSocketDisconnect

@app.websocket("/ws")
async def handle_disconnect(websocket):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Got: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")
        # Cleanup...
```

---

## 🔌 En Router

```python
from tachyon_api import Tachyon, Router

router = Router(prefix="/api/v1")

@router.websocket("/notifications")
async def notifications(websocket):
    await websocket.accept()
    await websocket.send_json({"type": "connected"})
    # ...

app = Tachyon()
app.include_router(router)

# Conectar a: ws://localhost:8000/api/v1/notifications
```

---

## 📦 JSON Messages

```python
@app.websocket("/ws/json")
async def json_ws(websocket):
    await websocket.accept()
    
    while True:
        # Recibir JSON
        data = await websocket.receive_json()
        
        # Procesar
        response = {
            "received": data,
            "processed": True,
            "echo": data.get("message", "")
        }
        
        # Enviar JSON
        await websocket.send_json(response)
```

### Cliente:
```javascript
ws.send(JSON.stringify({message: "Hello"}));
```

---

## 🔐 Autenticación

```python
@app.websocket("/ws/secure")
async def secure_ws(websocket):
    # Obtener token de query o headers
    token = websocket.query_params.get("token")
    
    # O de headers (antes de accept)
    # auth = websocket.headers.get("authorization")
    
    if not validate_token(token):
        await websocket.close(code=4001)  # Custom close code
        return
    
    await websocket.accept()
    await websocket.send_text("Authenticated!")
```

---

## 🧪 Testing

```python
from starlette.testclient import TestClient

def test_websocket():
    client = TestClient(app)
    
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("Hello")
        data = websocket.receive_text()
        assert data == "Echo: Hello"

def test_websocket_with_params():
    client = TestClient(app)
    
    with client.websocket_connect("/ws/room123") as websocket:
        data = websocket.receive_text()
        assert "room123" in data
```

---

## 📋 Códigos de Cierre

| Código | Significado |
|--------|-------------|
| 1000 | Normal closure |
| 1001 | Going away |
| 1002 | Protocol error |
| 1003 | Unsupported data |
| 1008 | Policy violation |
| 4000-4999 | Custom codes |

```python
await websocket.close(code=1000)  # Normal
await websocket.close(code=4001)  # Custom: unauthorized
```

---

## 🔗 Próximos Pasos

- [Testing](./11-testing.md) - Testear WebSockets
- [Best Practices](./15-best-practices.md) - Patrones recomendados
