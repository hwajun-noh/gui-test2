import json
from PyQt5.QtCore import QObject, QUrl, pyqtSignal
from PyQt5.QtWebSockets import QWebSocket

class WebSocketManager(QObject):
    messageReceived = pyqtSignal(dict) # Signal to emit parsed JSON messages
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.socket = QWebSocket()
        self.url = url

        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.textMessageReceived.connect(self._on_message_received)
        self.socket.error.connect(self._on_error)

    def connect(self):
        print(f"[WebSocket] Connecting to {self.url}...")
        self.socket.open(QUrl(self.url))

    def send_message(self, message: dict):
        if self.socket.isValid():
            self.socket.sendTextMessage(json.dumps(message))
        else:
            print("[WebSocket] Cannot send message, socket not valid.")
            
    def close(self):
         if self.socket.isValid():
              print("[WebSocket] Closing connection.")
              self.socket.close()

    def _on_connected(self):
        print("[WebSocket] Connected!")
        self.connected.emit()

    def _on_disconnected(self):
        print("[WebSocket] Disconnected.")
        self.disconnected.emit()
        # Optional: Implement reconnection logic here
        # QtCore.QTimer.singleShot(5000, self.connect) 

    def _on_message_received(self, message: str):
        print(f"[WebSocket] Message received: {message}")
        try:
            parsed_message = json.loads(message)
            self.messageReceived.emit(parsed_message)
        except json.JSONDecodeError:
            print(f"[WebSocket] Error decoding JSON: {message}")
            
    def _on_error(self, error_code):
         print(f"[WebSocket] Error: {error_code} - {self.socket.errorString()}") 