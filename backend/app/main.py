from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
import asyncio, json, os, io, wave, concurrent.futures as fut, numpy as np
from datetime import datetime, timedelta
from faster_whisper import WhisperModel
from translatepy.translators.google import GoogleTranslate

SAMPLE_RATE        = 16_000
CHANNELS           = 1
SAMPLE_WIDTH       = 2
CHUNK_MS           = 32
RECORD_TIMEOUT_MS  = 2_000
PHRASE_TIMEOUT_MS  = 3_000
TARGET_LANG        = "en"
MODEL_NAME         = os.getenv("WHISPER_MODEL", "large")
DEVICE             = "cuda"
COMPUTE_TYPE       = "auto"
TP_ASR             = 1
TP_TRANSLATE       = 4

asr_model = WhisperModel(
    MODEL_NAME,
    device=DEVICE,
    compute_type=COMPUTE_TYPE,
    cpu_threads=os.cpu_count()
)
translator = GoogleTranslate()
tp_asr = fut.ThreadPoolExecutor(TP_ASR)
tp_tr = fut.ThreadPoolExecutor(TP_TRANSLATE)

app = FastAPI()
def is_silent(audio: np.ndarray, threshold: float = 0.01) -> bool:
    return np.sqrt(np.mean(audio**2)) < threshold

async def transcribe_async(raw_pcm: bytes) -> tuple[str, str]:
    """Run Whisper in a worker thread and return (text, detected_lang)."""
    def _run(buf: bytes):
        pcm16 = np.frombuffer(buf, dtype=np.int16)
        audio = pcm16.astype(np.float32) / 32768.0

        if is_silent(audio):
            return ("", "")

        segments, info = asr_model.transcribe(
            audio,
            word_timestamps=False,
            task="transcribe"
        )
        return "".join(seg.text for seg in segments).strip(), info.language

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(tp_asr, _run, raw_pcm)

async def translate_async(text: str, source_lang: str) -> str:
    def _translate():
        try:
            return translator.translate(text, TARGET_LANG, source_lang).result
        except Exception as e:
            print(f"Translation error: {e}")
            return text

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(tp_tr, _translate)


@app.websocket("/ws")
async def pcm_stream(ws: WebSocket):
    await ws.accept()
    last_phrase_ts = None
    buffer = bytearray()
    transcript_all = []
    translation_all = []

    try:
        while True:
            try:
                chunk = await ws.receive_bytes()
            except WebSocketDisconnect:
                break

            now = datetime.now()

            if last_phrase_ts and now - last_phrase_ts > timedelta(
                milliseconds=PHRASE_TIMEOUT_MS
            ):
                buffer.clear()

            last_phrase_ts = now
            buffer.extend(chunk)

            ms_in_buf = len(buffer) / (SAMPLE_RATE * SAMPLE_WIDTH) * 1000
            if ms_in_buf < RECORD_TIMEOUT_MS:
                continue

            pcm_to_decode = bytes(buffer)
            buffer.clear()

            text, detected_lang = await transcribe_async(pcm_to_decode)
            if not text:
                continue

            transcript_all.append(text)
            translation = await translate_async(text, detected_lang)
            translation_all.append(translation)

            await ws.send_text(json.dumps({
                "type": "final",
                "text": text,
                "translation": translation,
                "detected_lang": detected_lang,
                "transcript": " ".join(transcript_all),
                "translation_all": " ".join(translation_all)
            }, ensure_ascii=False))

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close(code=1000)
