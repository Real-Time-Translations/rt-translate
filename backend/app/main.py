from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
import json, numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi
from vosk import Model, KaldiRecognizer

app = FastAPI()

SAMPLE_RATE   = 16_000
CUTOFF_HZ     = 4_000
ORDER         = 6
CHUNK_SAMPLES = 512

sos         = butter(ORDER, CUTOFF_HZ / (0.5 * SAMPLE_RATE),
                     btype='low', output='sos')
zi_template = sosfilt_zi(sos).astype(np.float32)

def apply_filter(data_bytes: bytes, state):
    x = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float32)
    y, state[:] = sosfilt(sos, x, zi=state)
    return np.clip(y, -32768, 32767).astype(np.int16).tobytes(), state


asr_model = Model("model")


@app.websocket("/ws")
async def pcm_stream(ws: WebSocket) -> None:
    await ws.accept()
    zi          = zi_template.copy()
    rec         = KaldiRecognizer(asr_model, SAMPLE_RATE)
    rec.SetWords(True)

    transcript_so_far = ""

    try:
        while True:
            try:
                pcm_chunk = await ws.receive_bytes()
            except WebSocketDisconnect:
                break

            filtered, zi = apply_filter(pcm_chunk, zi)

            if rec.AcceptWaveform(filtered):
                res = json.loads(rec.Result())
                final_text = res.get("text", "").strip()
                if final_text:
                    transcript_so_far += (" " if transcript_so_far else "") + final_text

                await ws.send_text(json.dumps({
                    "type":       "final",
                    "text":       final_text,
                    "words":      res.get("result", []),
                    "transcript": transcript_so_far
                }))

            else:
                part = json.loads(rec.PartialResult())
                partial = part.get("partial", "").strip()
                if partial:
                    await ws.send_text(json.dumps({
                        "type":  "partial",
                        "text":  partial
                    }))

    finally:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close(code=1000)

