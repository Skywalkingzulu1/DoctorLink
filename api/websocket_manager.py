#!/usr/bin/env python3
"""
Simple WebSocket connection manager for real-time updates.

Supports both room-based (teleconsultation) and user-based (notifications) 
WebSocket connections.
"""

from typing import Dict, Set, Any
import json
from fastapi import WebSocket


class ConnectionManager:
    """
    Manages WebSocket connections grouped by user_id or room_id.
    """

    def __init__(self) -> None:
        # For general user notifications (e.g. appointment status changes)
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        # For specific teleconsultation rooms
        self.room_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int = None, room_id: int = None) -> None:
        """
        Accept and register a new WebSocket connection.
        """
        await websocket.accept()
        if user_id is not None:
            self.user_connections.setdefault(user_id, set()).add(websocket)
        if room_id is not None:
            self.room_connections.setdefault(room_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int = None, room_id: int = None) -> None:
        """
        Unregister a WebSocket connection.
        """
        if user_id is not None and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
        if room_id is not None and room_id in self.room_connections:
            self.room_connections[room_id].discard(websocket)

    async def send_personal_message(self, message: Any, user_id: int) -> None:
        """
        Send a message (dict or str) to all connections associated with a user.
        """
        connections = self.user_connections.get(user_id, set())
        if not connections:
            return

        payload = json.dumps(message) if isinstance(message, (dict, list)) else str(message)
        
        dead_connections = set()
        for connection in connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.add(connection)
        
        for dead in dead_connections:
            self.user_connections[user_id].discard(dead)

    async def broadcast(self, room_id: int, message: Any) -> None:
        """
        Send a message to everyone in a specific room.
        """
        connections = self.room_connections.get(room_id, set())
        if not connections:
            return

        payload = json.dumps(message) if isinstance(message, (dict, list)) else str(message)
        
        dead_connections = set()
        for connection in connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.add(connection)
        
        for dead in dead_connections:
            self.room_connections[room_id].discard(dead)


# Export a singleton manager instance for use throughout the application.
manager = ConnectionManager()
