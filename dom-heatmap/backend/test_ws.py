import asyncio
import websockets
import json

async def test_connection():
    uri = "ws://localhost:8000/ws/dom/AAPL"
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")
        # Receive 5 messages
        for i in range(5):
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Message {i+1}: Type={data.get('type')}, Bids={len(data['data']['bids'])}, Asks={len(data['data']['asks'])}")
            # print sample heat
            if data['data']['bids']:
                print(f"Top Bid Heat: {data['data']['bids'][0]['heat_intensity']}")

asyncio.run(test_connection())
