import { useEffect, useRef, useState } from "react";
import { BrowserAudioRecorder } from "./audioRecorder";
import { COASTAL_PRIORITY_LANGUAGES, type IndianLanguage } from "./indianLanguages";
import { useLanguage } from "./i18n/LanguageContext";
import { getKeyterms, applyCorrections } from "./maritimeVocabulary";

interface Props {
  open: boolean;
  onClose: () => void;
  onTranscriptReady: (transcript: string, languageCode?: string, isVoice?: boolean) => void;
  onInputReady?: (text: string, languageCode?: string) => void;
}

export function VoiceInputModal({ open, onClose, onTranscriptReady, onInputReady }: Props) {
  const { t } = useLanguage();

  // Auto-Detect is the default: catches any Indian language automatically!
  const [selectedLanguage, setSelectedLanguage] = useState<IndianLanguage>(
    () => COASTAL_PRIORITY_LANGUAGES[0] || { displayName: "Auto-Detect", nativeScript: "Auto", bcp47Code: "unknown", region: "auto" }
  );

  // Default to native regional transcribe so voice queries stay in their original language
  const [speechMode, setSpeechMode] = useState<"transcribe" | "translate">("transcribe");
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [detectedLang, setDetectedLang] = useState("");
  const [detectedLangCode, setDetectedLangCode] = useState("");


  const recorderRef = useRef<BrowserAudioRecorder | null>(null);
  const timerRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const amplitudeHistory = useRef<number[]>(new Array(36).fill(0.05));

  const isStartingRef = useRef(false);
  const recordingStartTimeRef = useRef(0);
  const pointerDownTimeRef = useRef(0);
  const isHoldingRef = useRef(false);
  const holdTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!open) {
      handleCancel();
    }
  }, [open]);

  // Waveform canvas rendering with smooth gradient
  const drawWaveform = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const bars = amplitudeHistory.current;
    const count = bars.length;
    const barWidth = Math.max(3, (w / count) * 0.65);
    const spacing = w / count;
    const centerY = h / 2;

    const grad = ctx.createLinearGradient(0, 0, w, h);
    if (isRecording) {
      grad.addColorStop(0, "#ef4444");
      grad.addColorStop(1, "#f97316");
    } else {
      grad.addColorStop(0, "#0b2545");
      grad.addColorStop(1, "#3b82f6");
    }
    ctx.fillStyle = grad;

    for (let i = 0; i < count; i++) {
      const barH = Math.max(4, bars[i] * h * 0.95);
      const x = i * spacing + (spacing - barWidth) / 2;
      const y = centerY - barH / 2;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barH, 3);
      ctx.fill();
    }
  };

  useEffect(() => {
    drawWaveform();
  }, [isRecording]);

  const startRecording = async () => {
    if (isStartingRef.current || isRecording) return;
    isStartingRef.current = true;
    setErrorMsg("");
    setTranscript("");
    setDetectedLang("");

    try {
      const rec = new BrowserAudioRecorder();
      recorderRef.current = rec;

      amplitudeHistory.current = new Array(36).fill(0.05);

      await rec.start((amp) => {
        amplitudeHistory.current.shift();
        amplitudeHistory.current.push(Math.max(0.05, Math.min(1.0, amp * 2.8)));
        drawWaveform();
      });

      setIsRecording(true);
      const start = Date.now();
      recordingStartTimeRef.current = start;
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = window.setInterval(() => {
        setElapsedMs(Date.now() - start);
      }, 100);
    } catch (err) {
      console.error("[VoiceInputModal] mic permission or audio start failed:", err);
      setErrorMsg(t("voice_error_mic"));
      recorderRef.current = null;
      setIsRecording(false);
    } finally {
      isStartingRef.current = false;
    }
  };

  const stopRecording = async () => {
    if (isStartingRef.current) {
      let waitCount = 0;
      while (isStartingRef.current && waitCount < 20) {
        await new Promise((resolve) => setTimeout(resolve, 50));
        waitCount++;
      }
    }

    if (!recorderRef.current) {
      setIsRecording(false);
      return;
    }

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsRecording(false);
    setIsProcessing(true);

    try {
      const elapsed = Date.now() - (recordingStartTimeRef.current || 0);
      if (elapsed < 600) {
        throw new Error("Audio was very short — please speak for at least 1-2 seconds");
      }

      const audioBlob = await recorderRef.current.stop();
      recorderRef.current = null;

      let langCode = selectedLanguage.bcp47Code;
      if (langCode === "or-IN") langCode = "od-IN";

      // Send to speech endpoint with auto-detect and translation
      const result = await sendToSpeechApi(audioBlob, langCode, speechMode);
      const rawText = result.transcript || "";
      if (!rawText.trim()) {
        throw new Error("No speech recognized. Please speak closer to your microphone.");
      }

      const corrected = applyCorrections(rawText);
      setTranscript(corrected);

      const resolvedCode = result.language_code || selectedLanguage.bcp47Code;
      setDetectedLangCode(resolvedCode);

      const detectedName =
        COASTAL_PRIORITY_LANGUAGES.find((l) => l.bcp47Code === result.language_code)?.displayName ||
        result.language_code ||
        "Indian Regional";

      setDetectedLang(
        speechMode === "translate"
          ? `${detectedName} → English`
          : detectedName
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error translating audio";
      setErrorMsg(msg);
    } finally {
      setIsProcessing(false);
    }
  };

  const handlePointerDown = () => {
    if (isProcessing) return;
    if (isRecording) {
      // Tap toggle mode: tapping while recording stops it
      stopRecording();
      return;
    }
    pointerDownTimeRef.current = Date.now();
    isHoldingRef.current = false;

    if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    holdTimerRef.current = window.setTimeout(() => {
      isHoldingRef.current = true;
    }, 350);

    startRecording();
  };

  const handlePointerUp = () => {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    const pressDuration = Date.now() - pointerDownTimeRef.current;
    if (isHoldingRef.current || pressDuration > 450) {
      stopRecording();
    }
  };

  const sendToSpeechApi = async (
    blob: Blob,
    languageCode: string,
    mode: "transcribe" | "translate"
  ): Promise<{ transcript: string; language_code?: string }> => {
    const formData = new FormData();
    formData.append("file", blob, "voice_recording.wav");
    formData.append("model", "saaras:v4");
    formData.append("language_code", languageCode);
    formData.append("mode", mode);
    formData.append("with_timestamps", "false");
    formData.append("keyterms", JSON.stringify(getKeyterms()));

    const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
    try {
      const resp = await fetch(`${API_BASE}/speech/transcribe`, {
        method: "POST",
        body: formData,
      });
      if (resp.ok) {
        return await resp.json();
      }
      const errData = await resp.json().catch(() => null);
      if (errData?.detail) {
        console.warn("[VoiceInputModal] backend error:", errData.detail);
      }
    } catch (netErr) {
      console.warn("[VoiceInputModal] proxy call failed, attempting direct fallback:", netErr);
    }

    // Direct fallback with Sarvam AI key
    const directResp = await fetch("https://api.sarvam.ai/speech-to-text", {
      method: "POST",
      headers: {
        "api-subscription-key": "sk_rlsmpryc_39CSSgULU6lMuom7Lkt8MvbI",
      },
      body: formData,
    });

    if (!directResp.ok) {
      if (directResp.status === 429) {
        throw new Error("Speech service busy — please try again in a moment");
      }
      const text = await directResp.text();
      throw new Error(`Speech API error (${directResp.status}): ${text.slice(0, 100)}`);
    }

    return await directResp.json();
  };

  const handleSend = () => {
    if (transcript.trim()) {
      const code = detectedLangCode || (selectedLanguage.bcp47Code !== "unknown" ? selectedLanguage.bcp47Code : undefined);
      onTranscriptReady(transcript.trim(), code, true);
      onClose();
    }
  };

  const handleInsertIntoInput = () => {
    if (transcript.trim()) {
      const code = detectedLangCode || (selectedLanguage.bcp47Code !== "unknown" ? selectedLanguage.bcp47Code : undefined);
      if (onInputReady) {
        onInputReady(transcript.trim(), code);
      } else {
        onTranscriptReady(transcript.trim(), code, true);
      }
      onClose();
    }
  };

  const handleCancel = () => {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    if (recorderRef.current) {
      recorderRef.current.stop().catch(() => {});
      recorderRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsRecording(false);
    setIsProcessing(false);
    setTranscript("");
    setErrorMsg("");
    setElapsedMs(0);
    onClose();
  };

  if (!open) return null;

  const seconds = Math.floor((elapsedMs / 1000) % 60);
  const minutes = Math.floor(elapsedMs / 1000 / 60);
  const timerStr = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  return (
    <div className="voice-sheet-backdrop" onClick={handleCancel}>
      <div className="voice-sheet surface" onClick={(e) => e.stopPropagation()}>
        {/* Sliding drawer handle */}
        <div className="voice-sheet__handle" onClick={handleCancel} title="Close drawer" />

        {/* Header Bar */}
        <div className="voice-sheet__top-bar">
          <div className="voice-sheet__title-row">
            <span className="voice-sheet__title">JalJeev Voice Assistant</span>
            <span className="voice-sheet__badge">Auto-Detect and Translate</span>
          </div>
          <button
            type="button"
            className="voice-sheet__close-btn"
            onClick={handleCancel}
            title="Close"
            aria-label="Close voice assistant"
          >
            ✕
          </button>
        </div>

        {/* Translation Mode & Language Selection Bar */}
        <div className="voice-sheet__controls-bar">
          <div className="voice-sheet__mode-pills">
            <button
              type="button"
              className={`voice-sheet__mode-pill ${speechMode === "transcribe" ? "voice-sheet__mode-pill--active" : ""}`}
              onClick={() => setSpeechMode("transcribe")}
              disabled={isRecording || isProcessing}
              title="Speak in any regional language (Odia, Tamil, Hindi, etc.)"
            >
              Regional Language
            </button>
            <button
              type="button"
              className={`voice-sheet__mode-pill ${speechMode === "translate" ? "voice-sheet__mode-pill--active" : ""}`}
              onClick={() => setSpeechMode("translate")}
              disabled={isRecording || isProcessing}
              title="Automatically translate regional speech to English"
            >
              Translate to English
            </button>
          </div>

          <select
            className="voice-sheet__lang-select"
            value={selectedLanguage.bcp47Code}
            onChange={(e) => {
              const found = COASTAL_PRIORITY_LANGUAGES.find((l) => l.bcp47Code === e.target.value);
              if (found) setSelectedLanguage(found);
            }}
            disabled={isRecording || isProcessing}
            title="Speech language (Auto-Detect catches all Indian languages)"
          >
            {COASTAL_PRIORITY_LANGUAGES.map((l) => (
              <option key={l.bcp47Code} value={l.bcp47Code}>
                {l.nativeScript} — {l.displayName}
              </option>
            ))}
          </select>
        </div>

        {/* Waveform & Stopwatch Box */}
        <div className="voice-sheet__waveform-box">
          <canvas ref={canvasRef} width={440} height={48} className="voice-sheet__waveform" />
          {isRecording && (
            <div className="voice-sheet__timer-pill">
              <span>●</span> {timerStr} Recording...
            </div>
          )}
        </div>

        {/* Main Mic Record Button */}
        <div className="voice-sheet__btn-container">
          <button
            type="button"
            className={`voice-sheet__mic-btn ${isRecording ? "active" : ""}`}
            onMouseDown={handlePointerDown}
            onMouseUp={handlePointerUp}
            onTouchStart={(e) => {
              e.preventDefault();
              handlePointerDown();
            }}
            onTouchEnd={(e) => {
              e.preventDefault();
              handlePointerUp();
            }}
            disabled={isProcessing}
            aria-label={isRecording ? "Stop recording" : "Start speaking"}
          >
            <svg viewBox="0 0 24 24" width="42" height="42" fill="currentColor">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          </button>
          <div className="voice-sheet__mic-hint">
            {isRecording ? (
              <span style={{ color: "#ef4444", fontWeight: 600 }}>Tap button to stop and translate</span>
            ) : isProcessing ? (
              <span style={{ color: "var(--brand, #0b2545)", fontWeight: 600 }}>Translating your voice with AI...</span>
            ) : (
              <span>Tap to speak in Hindi, Odia, Tamil, Bengali, Telugu, Gujarati, Marathi, etc.</span>
            )}
          </div>
        </div>

        {/* Live Status Hint */}
        <div className="voice-sheet__status-badge">
          {errorMsg ? (
            <span style={{ color: "var(--risk-high, #ef4444)", fontWeight: 500 }}>{errorMsg}</span>
          ) : isRecording ? (
            <span style={{ color: "#ef4444", fontWeight: 600 }}>Listening to your voice...</span>
          ) : isProcessing ? (
            <span style={{ color: "#0b2545", fontWeight: 500 }}>Processing and translating...</span>
          ) : detectedLang ? (
            <span style={{ color: "#10b981", fontWeight: 600 }}>{detectedLang}</span>
          ) : (
            <span style={{ color: "var(--ink-2, #64748b)" }}>Speaks any Indian regional language</span>
          )}
        </div>

        {/* Translation & Transcript Preview Card */}
        <div className="voice-sheet__transcript-card">
          <div className="voice-sheet__transcript-meta">
            <span>{speechMode === "translate" ? "Translated Query (English)" : "Transcribed Query"}</span>
            {transcript && (
              <button
                type="button"
                style={{ background: "none", border: "none", color: "var(--ink-2, #64748b)", cursor: "pointer", fontSize: "11px" }}
                onClick={() => {
                  setTranscript("");
                  setDetectedLang("");
                }}
              >
                Clear
              </button>
            )}
          </div>
          {transcript ? (
            <div className="voice-sheet__transcript-text">{transcript}</div>
          ) : (
            <div className="voice-sheet__transcript-empty">
              Speak anything — your translated query will appear here automatically.
            </div>
          )}
        </div>

        {/* ALWAYS-VISIBLE ACTION BAR (Prominent "Send Now" button) */}
        <div className="voice-sheet__action-bar">
          <button
            type="button"
            className="voice-sheet__insert-btn"
            onClick={handleInsertIntoInput}
            disabled={!transcript.trim() || isProcessing}
            title={transcript.trim() ? "Insert translated text into the chat input bar" : "Speak first to generate text"}
          >
            Put in Chat Box
          </button>

          <button
            type="button"
            className="voice-sheet__send-btn"
            onClick={handleSend}
            disabled={!transcript.trim() || isProcessing}
            title={transcript.trim() ? "Send query directly to JalJeev" : "Speak first to enable Send Now"}
          >
            Send Now
          </button>
        </div>

        {/* Footer cancel / close link */}
        <button type="button" className="voice-sheet__footer-cancel" onClick={handleCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
