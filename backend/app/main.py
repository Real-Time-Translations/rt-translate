from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import noisereduce as nr
import numpy as np
import soundfile as sf


app = FastAPI()

def denoise_chunk(chunk_bytes, sr=16000):
    audio = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)
    reduced = nr.reduce_noise(y=audio, sr=sr)
    return reduced.astype(np.int16).tobytes()

def save_wav_from_raw():
    with open("output.raw", "rb") as f:
        raw = f.read()
    audio = np.frombuffer(raw, dtype=np.int16)
    sf.write("output.wav", audio, 44100)
    print(" WAV saved as output.wav")

@app.websocket("/ws")
async def pcm_stream(ws: WebSocket):
    await ws.accept()
    f = open('output.raw', 'wb')
    try:
        while True:
            data = await ws.receive_bytes()
            print(f"Received audio chunk ({len(data)} bytes)", flush=True)
            cleaned = denoise_chunk(data, sr=44100)
            f.write(cleaned)
            #f.write(data)
            #await ws.send_bytes(data)
            await ws.send_bytes(cleaned)
    except WebSocketDisconnect:
        print("client disconnected")
        f.close()
        save_wav_from_raw()
