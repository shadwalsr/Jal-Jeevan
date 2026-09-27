/**
 * Browser AudioRecorder capturing clean 16kHz mono 16-bit PCM WAV.
 * Emits real-time amplitude for live waveform visualizer.
 * Resamples from device native rate (44.1k/48k) to 16kHz for Sarvam AI.
 */
export class BrowserAudioRecorder {
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private input: MediaStreamAudioSourceNode | null = null;
  private muteGain: GainNode | null = null;
  private pcmData: Float32Array[] = [];
  private inputSampleRate = 48000;
  private targetSampleRate = 16000;
  private onAmplitudeCallback?: (amp: number) => void;

  async start(onAmplitude?: (amp: number) => void): Promise<void> {
    this.onAmplitudeCallback = onAmplitude;
    this.pcmData = [];

    // Request audio stream with browser speech optimizations
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

    // Do NOT force sampleRate in constructor — use device native rate to prevent
    // NotSupportedError / silence on Windows / Android WASAPI audio drivers.
    this.audioContext = new AudioContextClass();
    this.inputSampleRate = this.audioContext.sampleRate;

    // Crucial: Chromium browsers start newly created AudioContexts in 'suspended'
    // state unless explicitly resumed within a user interaction.
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    this.input = this.audioContext.createMediaStreamSource(this.mediaStream);

    // 4096 buffer size, 1 input channel, 1 output channel
    this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

    this.processor.onaudioprocess = (e) => {
      const channel = e.inputBuffer.getChannelData(0);
      // Copy Float32Array since audio buffer is reused by browser
      this.pcmData.push(new Float32Array(channel));

      // Calculate instantaneous peak amplitude for live waveform
      let max = 0;
      for (let i = 0; i < channel.length; i++) {
        const val = Math.abs(channel[i]);
        if (val > max) max = val;
      }
      this.onAmplitudeCallback?.(max);
    };

    // ScriptProcessorNode must connect to a destination to pull audio data in Chrome,
    // but connecting to destination directly causes mic feedback howl. We insert a
    // GainNode with gain=0 to silently satisfy the audio graph.
    this.muteGain = this.audioContext.createGain();
    this.muteGain.gain.value = 0;

    this.input.connect(this.processor);
    this.processor.connect(this.muteGain);
    this.muteGain.connect(this.audioContext.destination);
  }

  async stop(): Promise<Blob> {
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.muteGain) {
      this.muteGain.disconnect();
      this.muteGain = null;
    }
    if (this.input) {
      this.input.disconnect();
      this.input = null;
    }
    if (this.audioContext) {
      try {
        await this.audioContext.close();
      } catch {
        // ignore already closed
      }
      this.audioContext = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    // Flatten all recorded PCM chunks
    let totalLength = 0;
    for (const chunk of this.pcmData) {
      totalLength += chunk.length;
    }
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of this.pcmData) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    // Downsample from hardware rate (e.g. 44100 or 48000) to 16000 Hz for Sarvam AI
    const downsampled = this.downsampleBuffer(
      merged,
      this.inputSampleRate,
      this.targetSampleRate
    );

    // Convert Float32 to 16-bit PCM and format as valid WAV
    return this.encodeWAV(downsampled, this.targetSampleRate);
  }

  private downsampleBuffer(
    buffer: Float32Array,
    inputRate: number,
    outputRate: number
  ): Float32Array {
    if (inputRate === outputRate || buffer.length === 0) return buffer;
    const sampleRateRatio = inputRate / outputRate;
    const newLength = Math.round(buffer.length / sampleRateRatio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;

    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
      let accum = 0;
      let count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = count > 0 ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  private encodeWAV(samples: Float32Array, sampleRate: number): Blob {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    // RIFF identifier
    this.writeString(view, 0, "RIFF");
    // file length
    view.setUint32(4, 36 + samples.length * 2, true);
    // RIFF type
    this.writeString(view, 8, "WAVE");
    // format chunk identifier
    this.writeString(view, 12, "fmt ");
    // format chunk length
    view.setUint32(16, 16, true);
    // sample format (1 = raw PCM)
    view.setUint16(20, 1, true);
    // channel count (1 = mono)
    view.setUint16(22, 1, true);
    // sample rate
    view.setUint32(24, sampleRate, true);
    // byte rate (sampleRate * 1 * 16 / 8)
    view.setUint32(28, sampleRate * 2, true);
    // block align (1 * 16 / 8)
    view.setUint16(32, 2, true);
    // bits per sample
    view.setUint16(34, 16, true);
    // data chunk identifier
    this.writeString(view, 36, "data");
    // data chunk length
    view.setUint32(40, samples.length * 2, true);

    // Write 16-bit PCM samples with clipping protection
    let index = 44;
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      index += 2;
    }

    return new Blob([view], { type: "audio/wav" });
  }

  private writeString(view: DataView, offset: number, string: string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }
}

