<template>
	<div>
		<button @click="startStreaming">Start PCM Streaming</button>
		<button @click="stopStreaming">Stop Streaming</button>
	</div>
</template>

<script setup>
import { ref } from 'vue';

const socket = ref(null);
let audioCtx, processor, stream;

async function startStreaming () {
    stream     = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx   = new AudioContext();
    await audioCtx.resume();

    const input = audioCtx.createMediaStreamSource(stream);
    processor   = audioCtx.createScriptProcessor(4096, 1, 1);

    socket.value            = new WebSocket('ws://localhost:8000/ws');
    socket.value.binaryType = 'arraybuffer';
    socket.value.onopen     = () => console.log('ws open');
    socket.value.onerror    = (e) => console.error('ws error', e);
    socket.value.onclose    = () => console.log('ws closed');

    processor.onaudioprocess = ({ inputBuffer }) => {
      if (socket.value.readyState !== WebSocket.OPEN) return;

      const f32 = inputBuffer.getChannelData(0);
      const i16 = new Int16Array(f32.length);
      for (let i = 0; i < f32.length; i++) {
        const s = Math.max(-1, Math.min(1, f32[i]));
        i16[i]  = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      socket.value.send(i16.buffer.slice(0));
    };

    input.connect(processor);

    processor.connect(audioCtx.destination);
}

function stopStreaming () {
  processor?.disconnect();
  stream?.getTracks().forEach(t => t.stop());
  audioCtx?.close();
  socket.value?.close();
}
</script>
