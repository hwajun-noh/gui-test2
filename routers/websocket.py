import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

connected_clients: List[WebSocket] = []

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # 클라이언트로부터 메시지를 받을 필요가 없다면 receive 부분을 제거하거나 주석 처리할 수 있습니다.
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception as e:
        # 필요하다면 다른 예외 처리 추가
        print(f"WebSocket error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def broadcast_update():
    """
    데이터 변경 시 WebSocket 통해 모든 클라이언트에 reload 요청
    """
    message = json.dumps({"type": "reload"}, ensure_ascii=False)
    # 연결이 끊어진 클라이언트가 있을 수 있으므로 반복 중 예외 처리
    disconnected_clients = []
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            # 전송 실패 시 해당 클라이언트를 제거 목록에 추가
            disconnected_clients.append(client)
    
    # 연결 끊어진 클라이언트 제거
    for client in disconnected_clients:
        if client in connected_clients:
            connected_clients.remove(client)

# WebSocket 라우터를 위한 APIRouter 인스턴스 생성 (server.py에서 include_router)
from fastapi import APIRouter
router = APIRouter()

router.add_websocket_route("/ws", websocket_endpoint) 