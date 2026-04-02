import asyncio
import websockets
import json

async def listen():
    uri = "ws://localhost:8000/ws/events"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket.")
            # Keep listening
            while True:
                message = await websocket.recv()
                try:
                    data = json.loads(message)
                    print(f"Received via WS: {data['event']} from {data['agent']}")
                except:
                    print(f"Received via WS: {message}")
    except Exception as e:
        print(f"WS error: {e}")

if __name__ == "__main__":
    asyncio.run(listen())
