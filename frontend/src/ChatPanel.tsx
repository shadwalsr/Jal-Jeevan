import { useEffect, useRef, useState } from "react";
import { sendChat, type ChatResponse } from "./api";

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
const PIPELINE = [
  "parse_intent",
  "resolve_location",
  "execute_tools · weather · ocean · geo",
  "synthesize_answer",
];
const STEP_MS = 900;
const ESTIMATED_MS = 5000;
const MAX_FILL = 0.92;

function ThinkingState() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const id = window.setInterval(() => setElapsed(Date.now() - started), 200);
    return () => window.clearInterval(id);
  }, []);

  const step = Math.min(Math.floor(elapsed / STEP_MS), PIPELINE.length - 1);
  const fill = Math.min(elapsed / ESTIMATED_MS, MAX_FILL) * 100;

  return (
    <div className="reply">
      <div className="thinking">
        <div className="thinking__node" aria-live="polite">
          {PIPELINE[step]}
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
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [showTrace, setShowTrace] = useState<number | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  // Newest at the bottom, so the log follows the conversation down.
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    try {
      const resp = await sendChat(text, sessionId, clientLocation);
      setSessionId(resp.session_id);
      setMessages((m) => [...m, { role: "assistant", text: resp.answer, response: resp }]);
      const data = resp.data as { lat?: number; lon?: number; origin_lat?: number; origin_lon?: number };
      const lat = data.lat ?? data.origin_lat;
      const lon = data.lon ?? data.origin_lon;
      if (typeof lat === "number" && typeof lon === "number") {
        onLocationResolved(lat, lon);
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
          Hide — see map
        </button>
      </div>

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
                      <span>Not permitted — do not go</span>
                    </div>
                    <div className="risk-veto__reasons">
                      Vetoed before scoring, so no risk score exists. Scoring only runs on points
                      that pass the legal and survivability checks.
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
                    <span>
                      {evidence?.sources_used?.length ?? 0} sources
                    </span>
                    {(evidence?.data_gaps?.length ?? 0) > 0 && (
                      <>
                        <span className="meta-divider" />
                        <span>{evidence?.data_gaps.length} gaps</span>
                      </>
                    )}
                    <span className="meta-divider" />
                    <button className="link-btn" onClick={() => setShowTrace(showTrace === i ? null : i)}>
                      {showTrace === i ? "Hide reasoning" : "Reasoning"}
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
                          Open in Maps
                        </a>
                      </>
                    )}
                  </div>
                )}

                {showTrace === i && m.response && (
                  <div>
                    <div className="evidence-section__title">Planner trace</div>
                    <div className="evidence-section__rule" />
                    <ul className="evidence-list mono" style={{ fontSize: 12 }}>
                      {m.response.trace.map((line, j) => (
                        <li key={j}>{line}</li>
                      ))}
                    </ul>

                    {(evidence?.factor_lines?.length ?? 0) > 0 && (
                      <>
                        <div className="evidence-section__title" style={{ marginTop: 12 }}>
                          Risk factors
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
                          Sources
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
                          Data gaps
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
          Ask about marine conditions, safety, or where to go
        </label>
        <input
          id="chat-input"
          className="chat-bar__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={
            locationStatus === "granted"
              ? "Ask about conditions, safety, or where to go"
              : "Ask about conditions, or name a place"
          }
          disabled={loading}
        />
        <button className="chat-bar__send" onClick={handleSend} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
