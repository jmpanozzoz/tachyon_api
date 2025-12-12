"""
WebSocket connection manager for real-time notifications.

This manages WebSocket connections for each customer,
allowing us to send real-time KYC status updates.
"""

from typing import Dict, List, Any


class WebSocketManager:
    """
    Manages WebSocket connections grouped by customer ID.
    
    This allows sending targeted notifications to specific customers
    when their KYC verification status changes.
    """
    
    def __init__(self):
        # Map of customer_id -> list of WebSocket connections
        self._connections: Dict[str, List[Any]] = {}
    
    async def connect(self, websocket, customer_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        if customer_id not in self._connections:
            self._connections[customer_id] = []
        
        self._connections[customer_id].append(websocket)
    
    def disconnect(self, websocket, customer_id: str) -> None:
        """Remove a WebSocket connection."""
        if customer_id in self._connections:
            if websocket in self._connections[customer_id]:
                self._connections[customer_id].remove(websocket)
            
            # Clean up empty lists
            if not self._connections[customer_id]:
                del self._connections[customer_id]
    
    async def disconnect_all(self) -> None:
        """Close all WebSocket connections (for shutdown)."""
        for customer_id, connections in self._connections.items():
            for websocket in connections:
                try:
                    await websocket.close()
                except Exception:
                    pass
        self._connections.clear()
    
    async def send_to_customer(self, customer_id: str, message: dict) -> None:
        """
        Send a message to all connections for a specific customer.
        
        Args:
            customer_id: The customer to notify
            message: The message payload to send
        """
        connections = self._connections.get(customer_id, [])
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                # Connection might be closed, will be cleaned up on disconnect
                pass
    
    async def broadcast(self, message: dict) -> None:
        """Send a message to all connected clients."""
        for customer_id in self._connections:
            await self.send_to_customer(customer_id, message)
    
    def get_connection_count(self, customer_id: str = None) -> int:
        """Get the number of active connections."""
        if customer_id:
            return len(self._connections.get(customer_id, []))
        return sum(len(conns) for conns in self._connections.values())
    
    async def notify_verification_status(
        self,
        customer_id: str,
        verification_id: str,
        status: str,
        details: dict = None,
    ) -> None:
        """
        Send a verification status update notification.
        
        This is called by the verification service when status changes.
        """
        await self.send_to_customer(customer_id, {
            "type": "verification_status",
            "verification_id": verification_id,
            "status": status,
            "details": details or {},
        })


# Global manager instance
manager = WebSocketManager()
