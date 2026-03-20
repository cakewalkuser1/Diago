"""
WebSocket tracking hub for Uber-style live mechanic location.
Customers connect to ws /api/v1/tracking/{job_id} to receive location updates.
Mechanics POST to /api/v1/tracking/{job_id}/location to broadcast.
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.deps import get_db_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# job_id -> set of WebSocket connections (in-memory; use Redis in production)
_tracking_connections: Dict[int, Set[WebSocket]] = {}
_lock = asyncio.Lock()


async def _add_connection(job_id: int, ws: WebSocket) -> None:
    async with _lock:
        if job_id not in _tracking_connections:
            _tracking_connections[job_id] = set()
        _tracking_connections[job_id].add(ws)


async def _remove_connection(job_id: int, ws: WebSocket) -> None:
    async with _lock:
        if job_id in _tracking_connections:
            _tracking_connections[job_id].discard(ws)
            if not _tracking_connections[job_id]:
                del _tracking_connections[job_id]


async def broadcast_location(job_id: int, payload: dict) -> None:
    """Broadcast location update to all clients watching this job."""
    async with _lock:
        conns = list(_tracking_connections.get(job_id, []))
    if not conns:
        return
    msg = json.dumps(payload)
    dead = []
    for ws in conns:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        async with _lock:
            if job_id in _tracking_connections:
                _tracking_connections[job_id].discard(ws)


@router.websocket("/{job_id:int}")
async def tracking_websocket(websocket: WebSocket, job_id: int):
    """
    Customer connects to receive live mechanic location updates.
    Messages: { type: "location", latitude, longitude, heading?, speed_mph?, eta_min? }
    """
    await websocket.accept()
    await _add_connection(job_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await _remove_connection(job_id, websocket)


class LocationUpdate(BaseModel):
    """Mechanic location broadcast."""
    latitude: float
    longitude: float
    heading: float | None = None
    speed_mph: float | None = None
    eta_min: float | None = None


@router.post("/{job_id:int}/location")
async def post_location(
    job_id: int,
    payload: LocationUpdate,
    db=Depends(get_db_manager),
):
    """
    Mechanic (or mobile app) posts location. Broadcasts to all WebSocket clients watching this job.
    """
    cursor = db.connection.execute(
        "SELECT id, status, assigned_mechanic_id FROM jobs WHERE id = ?",
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    # Optionally verify mechanic is assigned; for now allow any location post
    data = {
        "type": "location",
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "heading": payload.heading,
        "speed_mph": payload.speed_mph,
        "eta_min": payload.eta_min,
    }
    await broadcast_location(job_id, data)
    # Persist to mechanic_location_log for replay
    try:
        mechanic_id = row["assigned_mechanic_id"]
        if mechanic_id:
            db.connection.execute(
                """INSERT INTO mechanic_location_log (job_id, mechanic_id, latitude, longitude, heading, speed_mph)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (job_id, mechanic_id, payload.latitude, payload.longitude, payload.heading, payload.speed_mph),
            )
            db.connection.commit()
    except Exception as e:
        logger.debug("Could not log location: %s", e)
    return {"ok": True}
