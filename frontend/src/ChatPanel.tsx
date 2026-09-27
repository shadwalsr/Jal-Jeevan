import { useEffect, useRef, useState } from "react";
import { sendChat, textToSpeech, type ChatResponse } from "./api";
import { useLanguage } from "./i18n/LanguageContext";
import { VoiceInputModal } from "./VoiceInputModal";

interface Message {
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
  isError?: boolean;
}

interface Props {
  onLocationResolved: (lat: number, lon: number) => void;
  // Browser geolocation, when granted (see App.tsx) — sent as a last-resort
  // fallback so "where can I go to fish?" (no place named) resolves against
  // where the user actually is, instead of going unanswered. A place named
  // in the message still wins; see graph.py's resolve_location.
  clientLocation: { lat: number; lon: number } | null;
  locationStatus: "requesting" | "granted" | "denied" | "unsupported";
  // Owned by App.tsx, not local state: the reopen tab lives outside this
  // component (see App.tsx for why — it has to sit on an ancestor that
  // never gets a CSS transform, and .chat-dock does), so both sides need to
  // agree on one source of truth.
  open: boolean;
  onRequestClose: () => void;
}

/**
 * The planner's fixed pipeline (app/planner/graph.py). Shown while a request
 * is in flight so a multi-second wait says what the system is doing instead of
 * showing a generic spinner.
 *
 * IMPORTANT, so nobody later mistakes this for telemetry: the trace only comes
 * back WITH the response, so this advances on elapsed time, not on live
 * status. It is accurate about the sequence — those four nodes always run, in
 * that order — and makes no claim about which one is executing right now. The
 * progress rule is an elapsed-time estimate and is capped below full for the
 * same reason: it must never appear to announce completion.
 */
const STEP_MS = 900;
const ESTIMATED_MS = 5000;
const MAX_FILL = 0.92;

function ThinkingState() {
  const { t } = useLanguage();
  const [elapsed, setElapsed] = useState(0);

  const pipeline = [
    t("pipeline_parse"),
    t("pipeline_resolve"),
    t("pipeline_execute"),
    t("pipeline_synthesize"),
  ];

  useEffect(() => {
    const started = Date.now();
    const id = window.setInterval(() => setElapsed(Date.now() - started), 200);
    return () => window.clearInterval(id);
  }, []);

  const step = Math.min(Math.floor(elapsed / STEP_MS), pipeline.length - 1);
  const fill = Math.min(elapsed / ESTIMATED_MS, MAX_FILL) * 100;

  return (
    <div className="reply">
      <div className="thinking">
        <div className="thinking__node" aria-live="polite">
          {pipeline[step]}
        </div>
        <div className="thinking__track">
          <div className="thinking__fill" style={{ width: `${fill}%` }} />
        </div>
      </div>
    </div>
  );
}

/**
 * The answer comes back as Markdown (the LLM writes "**Wave height:** 1.54 m"
 * and "- " bullets), but it was being rendered as plain text, so asterisks and
 * hyphens leaked into the UI. This is a DISPLAY transform only — it renders
 * bold and bullets and nothing else, and never interprets HTML, so an answer
 * cannot inject markup. Anything it does not recognise falls through as text,
 * which is the safe direction to fail.
 */
function renderAnswer(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const bullet = /^\s*[-*]\s+/.test(line);
    const content = bullet ? line.replace(/^\s*[-*]\s+/, "") : line;
    const parts = content.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
    const rendered = parts.map((part, j) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={j} style={{ fontWeight: 500 }}>
          {part.slice(2, -2)}
        </strong>
      ) : (
        <span key={j}>{part}</span>
      )
    );
    if (!content.trim()) return <div key={i} style={{ height: 6 }} />;
    return (
      <div key={i} className={bullet ? "answer-bullet" : undefined}>
        {rendered}
      </div>
    );
  });
}

function riskModifier(level: string): string {
  return level.toLowerCase();
}

export default function ChatPanel({
  onLocationResolved,
  clientLocation,
  locationStatus,
  open,
  onRequestClose,
}: Props) {
  const { language, t } = useLanguage();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [showTrace, setShowTrace] = useState<number | null>(null);
  const [voiceModalOpen, setVoiceModalOpen] = useState(false);
  const [playingMessageIdx, setPlayingMessageIdx] = useState<number | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Stop audio playback on unmount
  useEffect(() => {
    return () => {
      stopCurrentAudio();
    };
  }, []);

  // Newest at the bottom, so the log follows the conversation down.
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  const stopCurrentAudio = () => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setPlayingMessageIdx(null);
  };

  const playVoiceResponse = async (text: string, languageCode?: string, msgIdx?: number) => {
    stopCurrentAudio();
    if (typeof msgIdx === "number") {
      setPlayingMessageIdx(msgIdx);
    }

    const lang = languageCode || language.code || "hi-IN";

    try {
      // 1. Primary: Sarvam AI high-fidelity neural regional voice
      const ttsData = await textToSpeech(text, lang);
      if (ttsData.audio_base64) {
        const audio = new Audio("data:audio/wav;base64," + ttsData.audio_base64);
        currentAudioRef.current = audio;
        audio.onended = () => {
          setPlayingMessageIdx(null);
          currentAudioRef.current = null;
        };
        audio.onerror = () => {
          fallbackBrowserTTS(text, lang);
        };
        await audio.play();
        return;
      }
    } catch (err) {
      console.warn("[TTS] Sarvam TTS backend failed, falling back to browser speech synthesis:", err);
    }

    // 2. Fallback: Browser Web Speech API
    fallbackBrowserTTS(text, lang);
  };

  const fallbackBrowserTTS = (text: string, langCode: string) => {
    if (!window.speechSynthesis) {
      setPlayingMessageIdx(null);
      return;
    }
    try {
      const clean = text
        .replace(/\*\*([^*]+)\*\*/g, "$1")
        .replace(/[*#`_]/g, "")
        .replace(/\n+/g, ". ")
        .slice(0, 1000);
      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.rate = 0.95;
      if (langCode && langCode !== "unknown") {
        utterance.lang = langCode;
      }
      utterance.onend = () => setPlayingMessageIdx(null);
      utterance.onerror = () => setPlayingMessageIdx(null);
      window.speechSynthesis.speak(utterance);
    } catch {
      setPlayingMessageIdx(null);
    }
  };

  async function handleSend(overrideText?: string, explicitLang?: string, isVoice: boolean = false) {
    const text = (typeof overrideText === "string" ? overrideText : input).trim();
    if (!text || loading) return;
    setInput("");
    stopCurrentAudio();
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    try {
      const targetLang = explicitLang || language.code;
      const resp = await sendChat(text, sessionId, clientLocation, targetLang, isVoice);
      setSessionId(resp.session_id);
      const newAssistantIndex = messages.length + 1;
      setMessages((m) => [...m, { role: "assistant", text: resp.answer, response: resp }]);
      const data = resp.data as { lat?: number; lon?: number; origin_lat?: number; origin_lon?: number };
      const lat = data.lat ?? data.origin_lat;
      const lon = data.lon ?? data.origin_lon;
      if (typeof lat === "number" && typeof lon === "number") {
        onLocationResolved(lat, lon);
      }

      // Automatically read out the answer in the regional language if queried via voice!
      if (isVoice && resp.answer) {
        playVoiceResponse(resp.answer, resp.language_code || targetLang, newAssistantIndex);
      }
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: err instanceof Error ? err.message : String(err),
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }


  const hasContent = messages.length > 0 || loading;

  return (
    // inert (React 19+) keeps a closed widget out of the tab order and off
    // the accessibility tree — pointer-events:none alone stops clicks, but a
    // sighted keyboard user could otherwise still tab into a control that is
    // slid off-screen.
    <div className={`chat-widget${open ? "" : " chat-widget--closed"}`} inert={!open}>
      <div className="chat-widget__handle-row">
        <button className="btn chat-widget__hide" onClick={onRequestClose}>
          {t("hide_map")}
        </button>
      </div>

      {!hasContent && (
        <div className="chat-log surface" style={{ display: "flex", flexDirection: "column", gap: "8px", padding: "12px 14px", maxHeight: "160px", overflowY: "auto" }}>
          <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-2)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            {t("starter_questions_title")}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {[t("sample_q1"), t("sample_q2"), t("sample_q3"), t("sample_q4")].map((q, idx) => (
              <button
                key={idx}
                type="button"
                className="btn"
                style={{ fontSize: "12px", padding: "5px 10px", textAlign: "left", height: "auto", borderRadius: "14px", lineHeight: 1.3 }}
                onClick={() => handleSend(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {hasContent && (
        <div className="chat-log surface" ref={logRef}>
          {messages.map((m, i) => {
            if (m.role === "user") {
              return (
                <div key={i} className="reply">
                  <div className="reply__question">{m.text}</div>
                </div>
              );
            }

            const evidence = m.response?.evidence;
            const level = evidence?.risk_level ?? null;
            const vetoed = level === "REJECTED";

            return (
              <div key={i} className="reply reply--assistant">
                <div className={m.isError ? "reply__error" : "reply__answer"}>
                  {m.isError ? m.text : renderAnswer(m.text)}
                </div>

                {/* A veto is categorically different from a score: no number,
                    no chip, the same hatched language the map uses. */}
                {vetoed && (
                  <div className="risk-veto">
                    <div className="risk-veto__head">
                      <span className="risk-veto__swatch" />
                      <span>{t("vetoed_title")}</span>
                    </div>
                    <div className="risk-veto__reasons">
                      {t("vetoed_desc")}
                    </div>
                  </div>
                )}

                {!vetoed && level && evidence && (
                  <div className="reply__meta">
                    <span className={`risk-chip risk-chip--${riskModifier(level)}`}>
                      <span className="risk-chip__swatch" />
                      <span>
                        {level}
                        {evidence.risk_score != null ? ` ${evidence.risk_score}/100` : ""}
                      </span>
                    </span>
                    {evidence.location_lat != null && evidence.location_lon != null && (
                      <>
                        <span className="meta-divider" />
                        <span className="mono" style={{ fontSize: 13, color: "var(--ink-2)" }}>
                          {evidence.location_lat.toFixed(4)}, {evidence.location_lon.toFixed(4)}
                        </span>
                      </>
                    )}
                  </div>
                )}

                {m.response && (
                  <div className="reply__footer">
                    <button
                      type="button"
                      className={`voice-listen-btn ${playingMessageIdx === i ? "voice-listen-btn--playing" : ""}`}
                      onClick={() => {
                        if (playingMessageIdx === i) {
                          stopCurrentAudio();
                        } else {
                          playVoiceResponse(m.text, m.response?.language_code || language.code, i);
                        }
                      }}
                      title={playingMessageIdx === i ? "Stop voice readout" : "Listen in regional language"}
                      aria-label={playingMessageIdx === i ? "Stop voice readout" : "Listen in regional language"}
                    >
                      {playingMessageIdx === i ? (
                        <>
                          <span>⏹️</span>
                          <span>Stop</span>
                        </>
                      ) : (
                        <>
                          <span>🔊</span>
                          <span>Listen</span>
                        </>
                      )}
                    </button>
                    <span className="meta-divider" />
                    <span>
                      {evidence?.sources_used?.length ?? 0} {t("sources_count")}
                    </span>
                    {(evidence?.data_gaps?.length ?? 0) > 0 && (
                      <>
                        <span className="meta-divider" />
                        <span>{evidence?.data_gaps.length} {t("gaps_count")}</span>
                      </>
                    )}
                    <span className="meta-divider" />
                    <button className="link-btn" onClick={() => setShowTrace(showTrace === i ? null : i)}>
                      {showTrace === i ? t("hide_reasoning") : t("reasoning")}
                    </button>
                    {evidence?.location_maps_url && (
                      <>
                        <span className="meta-divider" />
                        <a
                          className="link-btn"
                          href={evidence.location_maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {t("open_in_maps")}
                        </a>
                      </>
                    )}
                  </div>
                )}

                {showTrace === i && m.response && (
                  <div>
                    <div className="evidence-section__title">{t("planner_trace")}</div>
                    <div className="evidence-section__rule" />
                    <ul className="evidence-list mono" style={{ fontSize: 12 }}>
                      {m.response.trace.map((line, j) => (
                        <li key={j}>{line}</li>
                      ))}
                    </ul>

                    {(evidence?.factor_lines?.length ?? 0) > 0 && (
                      <>
                        <div className="evidence-section__title" style={{ marginTop: 12 }}>
                          {t("risk_factors")}
                        </div>
                        <div className="evidence-section__rule" />
                        <ul className="evidence-list mono">
                          {evidence?.factor_lines.map((line, j) => (
                            <li key={j}>{line}</li>
                          ))}
                        </ul>
                      </>
                    )}

                    {(evidence?.sources_used?.length ?? 0) > 0 && (
                      <>
                        <div className="evidence-section__title" style={{ marginTop: 12 }}>
                          {t("sources_label")}
                        </div>
                        <div className="evidence-section__rule" />
                        <ul className="evidence-list mono" style={{ fontSize: 12 }}>
                          {evidence?.sources_used.map((s, j) => (
                            <li key={j}>{s}</li>
                          ))}
                        </ul>
                      </>
                    )}

                    {/* Never behind a further toggle: what we did not know is
                        part of the answer. */}
                    {(evidence?.data_gaps?.length ?? 0) > 0 && (
                      <>
                        <div className="evidence-section__title" style={{ marginTop: 12 }}>
                          {t("data_gaps")}
                        </div>
                        <div className="evidence-section__rule" />
                        <ul className="evidence-list evidence-gaps">
                          {evidence?.data_gaps.map((s, j) => (
                            <li key={j}>{s}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {loading && <ThinkingState />}
        </div>
      )}

      <div className="chat-bar">
        <label htmlFor="chat-input" className="visually-hidden">
          {t("ask_placeholder_default")}
        </label>
        <input
          ref={inputRef}
          id="chat-input"
          className="chat-bar__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={
            locationStatus === "granted"
              ? t("ask_placeholder_gps")
              : t("ask_placeholder_default")
          }
          disabled={loading}
        />
        <button
          type="button"
          className="chat-bar__mic"
          onClick={() => setVoiceModalOpen(true)}
          disabled={loading}
          title={t("voice_input")}
          aria-label={t("speak_query")}
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        </button>
        <button className="chat-bar__send" onClick={() => handleSend()} disabled={loading || !input.trim()}>
          {t("send")}
        </button>
      </div>

      <VoiceInputModal
        open={voiceModalOpen}
        onClose={() => setVoiceModalOpen(false)}
        onTranscriptReady={(transcript, langCode) => handleSend(transcript, langCode, true)}
        onInputReady={(transcript) => {
          setInput(transcript);
          setTimeout(() => inputRef.current?.focus(), 50);
        }}
      />
    </div>
  );
}
