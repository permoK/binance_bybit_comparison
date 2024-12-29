from flask import Flask, render_template, request
from flask_socketio import SocketIO
import websocket
import json
from threading import Thread
from datetime import datetime
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store the latest prices in memory
latest_prices = {
    'binance': {},
    'bybit': {}
}

# Configuration
TRADING_PAIRS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "THEUSDT",
]

# WebSocket endpoints
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"

class BinanceWebSocket:
    def __init__(self):
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(
            BINANCE_WS_URL,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 's' in data and 'c' in data:  # Binance ticker message format
                symbol = data['s']
                price = float(data['c'])
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                latest_prices['binance'][symbol] = {
                    'price': price,
                    'timestamp': timestamp
                }
                
                socketio.emit('price_update', latest_prices)
                
        except Exception as e:
            print(f"Binance message error: {e}")

    def on_error(self, ws, error):
        print(f"Binance WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("Binance WebSocket connection closed")
        time.sleep(5)  # Wait before reconnecting
        self.start()

    def on_open(self, ws):
        print("Binance WebSocket connection opened")
        # Subscribe to ticker streams
        streams = [f"{pair.lower()}@ticker" for pair in TRADING_PAIRS]
        subscribe_message = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }
        ws.send(json.dumps(subscribe_message))

    def start(self):
        self.ws.run_forever()

class BybitWebSocket:
    def __init__(self):
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(
            BYBIT_WS_URL,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )

    def on_message(self, ws, message):
        try:
            message = json.loads(message)
            if message.get('topic', '').startswith('tickers.'):
                data = message.get('data', {})
                if data:
                    symbol = data.get('symbol')
                    last_price = data.get('lastPrice')
                    
                    if symbol and last_price:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        latest_prices['bybit'][symbol] = {
                            'price': float(last_price),
                            'timestamp': timestamp
                        }
                        
                        socketio.emit('price_update', latest_prices)
                        
        except Exception as e:
            print(f"Bybit message error: {e}")

    def on_error(self, ws, error):
        print(f"Bybit WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("Bybit WebSocket connection closed")
        time.sleep(5)  # Wait before reconnecting
        self.start()

    def on_open(self, ws):
        print("Bybit WebSocket connection opened")
        # Subscribe to ticker channels
        for pair in TRADING_PAIRS:
            subscribe_message = {
                "op": "subscribe",
                "args": [f"tickers.{pair}"]
            }
            ws.send(json.dumps(subscribe_message))

    def start(self):
        self.ws.run_forever()

@app.route('/')
def index():
    return render_template('index.html', trading_pairs=TRADING_PAIRS)

@socketio.on('connect')
def handle_connect():
    if latest_prices:
        socketio.emit('price_update', latest_prices, room=request.sid)
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

def start_websockets():
    binance_ws = BinanceWebSocket()
    bybit_ws = BybitWebSocket()
    
    # Start WebSocket connections in separate threads
    Thread(target=binance_ws.start, daemon=True).start()
    Thread(target=bybit_ws.start, daemon=True).start()

def create_app():
    start_websockets()
    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host='0.0.0.0', port=5100)
