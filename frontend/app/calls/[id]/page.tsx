"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api, CallRecord, callLifecycleLabel, formatDuration, isCallLive, statusTone } from "@/lib/api";

export default function CallDetailsPage() {
  const { id } = useParams<{id:string}>();
  const [call,setCall] = useState<CallRecord|null>(null);
  const [error,setError] = useState("");
  const [now,setNow] = useState(Date.now());

  useEffect(()=>{
    let cancelled = false;
    async function refresh() {
      try {
        const next = await api.call(id);
        if (!cancelled) { setCall(next); setError(""); }
      } catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); }
    }
    refresh();
    const timer = window.setInterval(refresh, 2000);
    const clock = window.setInterval(()=>setNow(Date.now()), 1000);
    return ()=>{ cancelled = true; window.clearInterval(timer); window.clearInterval(clock); };
  },[id]);

  const displayDuration = useMemo(()=>{
    if (!call) return 0;
    if (!isCallLive(call) || !call.started_at) return call.duration_seconds;
    return Math.max(call.duration_seconds, Math.floor((now - new Date(call.started_at).getTime()) / 1000));
  },[call, now]);

  if(error && !call) return <div className="error">{error}</div>;
  if(!call) return <div className="loading"><span className="spinner"/> Loading call details…</div>;

  const summary = call.structured_summary || {};
  const callMode = String(call.agent_state?.call_mode || (call.provider_call_id?.startsWith("sim-") ? "browser" : "twilio"));
  const isReal = callMode === "twilio";
  const isLive = isCallLive(call);
  const lifecycle = callLifecycleLabel(call);

  const detailItems = [
    ["Customer",call.customer_name],
    ["Status",lifecycle],
    ["Duration",formatDuration(displayDuration)],
    ["Phone",call.phone_number],
    ["Outcome",call.outcome || (isLive ? "In progress" : "—")],
    ["Lead status",call.lead_status || "—"],
    ["Call mode",isReal ? "Real phone / Twilio" : "Browser voice demo"],
    ["Provider call ID",call.provider_call_id || "—"]
  ];

  return <>
    <header className="header detailHeader">
      <div>
        <div className="eyebrow">CALL SESSION</div>
        <h1>{isReal ? "Real phone call" : "Browser voice call"}</h1>
        <p>{isReal ? "Twilio handles the live phone connection while this page monitors lifecycle, transcript, and AI outcome." : "Review the browser voice demonstration, transcript, and generated qualification summary."}</p>
      </div>
      <div className="headerActions"><Link className="btn ghost" href="/">← Dashboard</Link>{!isReal && isLive && <Link className="btn primary" href={`/call/${call.id}`}>Open browser demo</Link>}</div>
    </header>

    {error && <div className="error"><strong>Refresh warning:</strong> {error}</div>}

    <section className={`callLifecycleBanner ${isLive ? "live" : "ended"}`}>
      <span className={isLive ? "pulseDot" : "endedIcon"}>{isLive ? "" : "✓"}</span>
      <div>
        <strong>{isLive ? `Live call · ${lifecycle}` : lifecycle}</strong>
        <span>{isLive ? "Status is synchronized with the backend every 2 seconds and reconciled with Twilio when needed." : `Call ended${call.ended_at ? ` at ${new Date(call.ended_at).toLocaleString()}` : ""}. Final transcript and summary are available below.`}</span>
      </div>
      <span className={`badge ${statusTone(call.status)}`}><span className="statusDot" />{isLive ? "Active" : "Ended"}</span>
    </section>

    <section className="detailGrid">{detailItems.map(([k,v],index)=><div className="detailBox" key={String(k)} style={{animationDelay:`${index*35}ms`}}><small>{k}</small><strong>{String(v)}</strong></div>)}</section>
    {call.error_message && <div className="error"><strong>{call.error_code || "Call error"}</strong>: {call.error_message}</div>}

    <section className="summaryGrid">
      <div className="card liftCard"><div className="cardHead"><div><h2>AI-generated summary</h2><span>{isLive ? "Generated automatically when the call ends" : "Structured qualification result"}</span></div><span className={`badge ${call.follow_up_required?"amber":"green"}`}>{isLive ? "Pending" : call.follow_up_required?"Follow-up required":"No follow-up"}</span></div><div className="cardBody">
        <p className="summaryText">{call.summary_text || (isLive ? "The call is active. The final summary will appear automatically after the phone call ends." : "No summary was generated for this call.")}</p>
        <div className="kv">{Object.entries(summary).map(([k,v])=><div className="kvRow" key={k}><span>{k.replaceAll("_"," ")}</span><strong>{Array.isArray(v) ? (v.length ? v.join(" · ") : "—") : typeof v === "object" ? JSON.stringify(v) : String(v ?? "—")}</strong></div>)}</div>
        {!isLive && Object.keys(summary).length===0 && <div className="empty compactEmpty">No structured fields were captured.</div>}
      </div></div>
      <div className="card liftCard"><div className="cardHead"><div><h2>{isLive ? "Live transcript" : "Complete transcript"}</h2><span>{call.turns.length} saved turns</span></div>{isLive && <span className="badge blue"><span className="statusDot"/>Auto-refreshing</span>}</div><div className="cardBody"><div className="transcript transcriptTall">{call.turns.length===0?<div className="empty">{isReal && isLive ? "Waiting for the customer to answer…" : "No transcript yet."}</div>:call.turns.map(t=><div key={t.id} className={`bubble ${t.speaker==="ai"?"ai":"customer"}`}><strong>{t.speaker==="ai" ? "AI Agent" : "Customer"}</strong>{t.message}<div className="turnTime">{new Date(t.created_at).toLocaleTimeString()}</div></div>)}</div></div></div>
    </section>
  </>;
}
