from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

@app.websocket("/ws")
async def pcm_stream(ws: WebSocket):
    await ws.accept()
    f = open('./output.raw', 'wb')
    try:
        while True:
            data = await ws.receive_bytes()
            print(f"Received audio chunk ({len(data)} bytes)", flush=True)
            f.write(data)
            await ws.send_bytes(data)
    except WebSocketDisconnect:
        print("client disconnected")
