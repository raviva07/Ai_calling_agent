"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, CallRecord, Turn, WS_BASE } from "@/lib/api";

const trackedFields = ["customer_name","company_name","requirement","application","ro_capacity","location","budget","timeline","additional_requirements"];

export default function BrowserCallPage() {
  const { id } = useParams<{id:string}>();
  const router = useRouter();
  const [call, setCall] = useState<CallRecord | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [state, setState] = useState<Record<string, unknown>>({});
  const [status, setStatus] = useState("Connecting to AI Calling Agent…");
  const [typed, setTyped] = useState("");
  const [micReady, setMicReady] = useState(false);
  const micReadyRef = useRef(false);
  const [listening, setListening] = useState(false);
  const [latestAgent, setLatestAgent] = useState("");
  const [error, setError] = useState("");
  const [ending, setEnding] = useState(false);
  const endingRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const recognitionRef = useRef<any>(null);
  const ttsActive = useRef(false);
  const pendingEndNavigation = useRef(false);

  useEffect(() => {
    let mounted = true;
    api.call(id).then(c => {
      if (!mounted) return;
      setCall(c);
      setTurns(c.turns);
      setState(c.agent_state || {});
      if (c.ended_at) router.replace(`/calls/${id}`);
    }).catch(e=>setError(e instanceof Error ? e.message : String(e)));

    const ws = new WebSocket(`${WS_BASE}/ws/calls/${id}`);
    wsRef.current = ws;
    ws.onopen = () => setStatus("AI Calling Agent connected");
    ws.onerror = () => setError("Realtime connection failed. Check that the FastAPI backend is running on port 8000.");
    ws.onclose = () => {
      if (mounted && !endingRef.current) setStatus(prev => prev.startsWith("Call ended") ? prev : "Realtime connection closed");
    };
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.type === "agent") {
        setLatestAgent(m.text);
        setState(m.state || {});
        setTurns(prev => [...prev, {id: crypto.randomUUID(), speaker:"ai", message:m.text, created_at:new Date().toISOString()}]);
        setStatus(m.should_end ? "Call objective completed" : "AI Calling Agent speaking");
        if (micReadyRef.current) speak(m.text, !m.should_end);
      }
      if (m.type === "ended") {
        endingRef.current = true;
        setEnding(true);
        setStatus("Call ended · summary generated");
        if (ttsActive.current) pendingEndNavigation.current = true;
        else router.push(`/calls/${id}`);
      }
      if (m.type === "error") setError(m.message);
    };
    return () => {
      mounted = false;
      ws.close();
      window.speechSynthesis?.cancel();
      recognitionRef.current?.stop?.();
    };
  }, [id, router]); // eslint-disable-line react-hooks/exhaustive-deps

  function setupRecognition() {
    const w = window as any;
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) {
      setError("Speech recognition is not available in this browser. Use Chrome/Edge or type the reply below.");
      return null;
    }
    const r = new Ctor();
    r.lang = "en-IN";
    r.interimResults = false;
    r.continuous = false;
    r.onstart = () => { setListening(true); setStatus("Listening to customer…"); };
    r.onend = () => setListening(false);
    r.onerror = (e:any) => {
      setListening(false);
      sendSocket({type:"event", event_type:"speech_recognition_event", details:{error:e.error}});
      if (e.error === "no-speech") sendCustomer("");
      else if (e.error !== "aborted") setError(`Speech recognition: ${e.error}`);
    };
    r.onresult = (e:any) => {
      const text = e.results?.[0]?.[0]?.transcript?.trim();
      sendCustomer(text || "");
    };
    recognitionRef.current = r;
    return r;
  }

  function sendSocket(payload: Record<string, unknown>) {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  }

  async function enableMic() {
    setError("");
    try {
      await navigator.mediaDevices.getUserMedia({audio:true});
      const r = setupRecognition();
      if (!r) return;
      setMicReady(true);
      micReadyRef.current = true;
      setStatus("Microphone ready");
      if (latestAgent) speak(latestAgent, true);
      else startListening(r);
    } catch {
      setError("Microphone permission was denied. You can still use typed replies for the demo.");
    }
  }

  function startListening(r = recognitionRef.current) {
    if (!r || listening || ending) return;
    try { r.start(); } catch { /* browser can throw if already starting */ }
  }

  function speak(text:string, listenAfter:boolean) {
    if (!("speechSynthesis" in window)) { if (listenAfter) startListening(); return; }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-IN";
    u.rate = 1.02;
    u.pitch = 1;
    ttsActive.current = true;
    u.onstart = () => setStatus("AI Calling Agent speaking");
    u.onend = () => {
      ttsActive.current = false;
      if (pendingEndNavigation.current) {
        pendingEndNavigation.current = false;
        router.push(`/calls/${id}`);
      } else if (listenAfter) startListening();
    };
    u.onerror = () => {
      ttsActive.current = false;
      if (pendingEndNavigation.current) {
        pendingEndNavigation.current = false;
        router.push(`/calls/${id}`);
      } else if (listenAfter) startListening();
    };
    window.speechSynthesis.speak(u);
  }

  function interruptAndTalk() {
    if (ending) return;
    if (ttsActive.current) {
      window.speechSynthesis.cancel();
      ttsActive.current = false;
      sendSocket({type:"event", event_type:"customer_interrupted_ai", details:{source:"browser_demo"}});
    }
    startListening();
  }

  function sendCustomer(text:string) {
    if (ending) return;
    if (!sendSocket({type:"user_text", text})) {
      setError("Realtime connection is not ready. Please reopen the browser demo from the call details page.");
      return;
    }
    setTurns(prev => [...prev, {id:crypto.randomUUID(), speaker:"customer", message:text || "[silence]", created_at:new Date().toISOString()}]);
    setStatus("AI Calling Agent is deciding the next action…");
  }

  function submitTyped(e:FormEvent) {
    e.preventDefault();
    const v = typed.trim();
    if (!v || ending) return;
    setTyped("");
    sendCustomer(v);
  }

  async function hangup() {
    if (ending) return;
    endingRef.current = true;
    setEnding(true);
    window.speechSynthesis.cancel();
    ttsActive.current = false;
    recognitionRef.current?.stop?.();
    setListening(false);
    setStatus("Ending call…");

    if (sendSocket({type:"hangup"})) return;

    // REST fallback prevents a broken/closed WebSocket from leaving this demo
    // permanently marked active.
    try {
      await api.endCall(id, "ended_by_customer");
      setStatus("Call ended · summary generated");
      router.push(`/calls/${id}`);
    } catch (e) {
      endingRef.current = false;
      setEnding(false);
      setError(e instanceof Error ? e.message : "Could not end the call cleanly");
    }
  }

  const initials = useMemo(()=>call?.customer_name?.split(" ").map(x=>x[0]).join("").slice(0,2).toUpperCase() || "AI",[call]);

  if (!call) return <div className="loading"><span className="spinner"/> Loading call… {error}</div>;

  return <>
    <header className="header detailHeader"><div><div className="eyebrow">BROWSER VOICE DEMO</div><h1>AI Calling Agent</h1><p>Two-way microphone → speech-to-text → AI response → text-to-speech demonstration.</p></div><Link className="btn ghost" href="/">← Dashboard</Link></header>
    {error && <div className="error" role="alert">{error}</div>}
    <div className="callLayout">
      <section className="callStage">
        <div className="callGlow" />
        <div className="callTop"><span className="badge darkBadge"><span className="statusDot"/>OUTBOUND · AI AGENT</span><span className="sessionId">#{call.id.slice(0,8)}</span></div>
        <div className={`avatar ${listening ? "listening" : ""}`}>{initials}</div>
        <h2>{call.customer_name}</h2><div className="phone">{call.phone_number}</div><div className="callStatus"><span className={listening ? "waveBars active" : "waveBars"}><i/><i/><i/><i/></span>{status}</div>
        <div className="callControls">
          {!micReady && <button className="roundBtn" onClick={enableMic} disabled={ending}>🎙 Enable mic</button>}
          {micReady && <button className="roundBtn" onClick={interruptAndTalk} disabled={ending}>{listening ? "● Listening" : "🎙 Interrupt & talk"}</button>}
          <button className="roundBtn" disabled={ending} onClick={()=>{window.speechSynthesis.cancel(); ttsActive.current=false; recognitionRef.current?.stop?.(); setListening(false); setStatus("Audio paused");}}>🔇 Pause audio</button>
          <button className="roundBtn end" onClick={hangup} disabled={ending}>☎ {ending ? "Ending…" : "End call"}</button>
        </div>
      </section>

      <aside className="callSidebar">
        <section className="card liftCard"><div className="cardHead"><div><h2>Live transcript</h2><span>Saved turn by turn</span></div><span className="badge blue">{turns.length} turns</span></div><div className="cardBody">
          <div className="transcript">{turns.length === 0 ? <div className="empty">Waiting for the conversation to begin…</div> : turns.map(t=><div key={t.id} className={`bubble ${t.speaker === "ai" ? "ai":"customer"}`}><strong>{t.speaker === "ai" ? "AI Agent":"Customer"}</strong>{t.message}</div>)}</div>
          <form className="typeRow" onSubmit={submitTyped}><input className="input" value={typed} disabled={ending} onChange={e=>setTyped(e.target.value)} placeholder="Type reply fallback…"/><button className="btn primary" disabled={ending || !typed.trim()}>Send</button></form>
        </div></section>
        <section className="card liftCard"><div className="cardHead"><div><h2>Agent memory</h2><span>Captured qualification fields</span></div></div><div className="cardBody progressList">
          {trackedFields.map(k=><div className="progressItem" key={k}><span>{k.replaceAll("_"," ")}</span><strong className={state[k] ? "captured" : "missing"}>{String(state[k] || "Missing")}</strong></div>)}
        </div></section>
      </aside>
    </div>
  </>;
}
