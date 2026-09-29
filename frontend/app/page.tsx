"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  api,
  CallRecord,
  callLifecycleLabel,
  Customer,
  DashboardStats,
  formatDuration,
  isCallLive,
  statusTone,
  TelephonyConfig,
} from "@/lib/api";

const emptyForm = { name: "", phone_number: "", company_name: "", purpose: "Product enquiry", product: "Commercial RO System" };
const emptyFilters = { customer: "", status: "", lead_status: "", follow_up_required: "", outcome: "", date: "" };

function statusBadge(call: CallRecord) {
  return <span className={`badge ${statusTone(call.status)}`}><span className="statusDot" />{callLifecycleLabel(call)}</span>;
}

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [telephony, setTelephony] = useState<TelephonyConfig | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState(emptyFilters);
  const [appliedQuery, setAppliedQuery] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function loadAll() {
    setRefreshing(true);
    try {
      const [s, c, h, t] = await Promise.all([api.stats(), api.customers(), api.calls(appliedQuery), api.telephonyConfig()]);
      setStats(s);
      setCustomers(c);
      setCalls(h);
      setTelephony(t);
      setLastUpdated(new Date());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load dashboard");
    } finally {
      setRefreshing(false);
    }
  }

  async function refreshCallData(query = appliedQuery, silent = false) {
    if (!silent) setRefreshing(true);
    try {
      const [s, h] = await Promise.all([api.stats(), api.calls(query)]);
      setStats(s);
      setCalls(h);
      setLastUpdated(new Date());
      setError("");
    } catch (e) {
      if (!silent) setError(e instanceof Error ? e.message : "Could not refresh calls");
    } finally {
      if (!silent) setRefreshing(false);
    }
  }

  useEffect(() => { loadAll(); /* initial load only */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") refreshCallData(appliedQuery, true);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [appliedQuery]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submitCustomer(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await api.createCustomer(form);
      setCustomers(prev => [created, ...prev]);
      setForm(emptyForm);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create customer");
    } finally {
      setBusy(false);
    }
  }

  async function startCall(customerId: string, mode: "browser" | "twilio") {
    setBusy(true);
    setError("");
    try {
      const call = await api.startCall(customerId, mode);
      if (call.status === "failed") throw new Error(call.error_message || "Calling provider failed");
      router.push(mode === "twilio" ? `/calls/${call.id}` : `/call/${call.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start call");
      setBusy(false);
    }
  }

  async function applyFilters() {
    const p = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) p.set(k, v); });
    const query = p.toString();
    setAppliedQuery(query);
    await refreshCallData(query);
  }

  async function resetFilters() {
    setFilters(emptyFilters);
    setAppliedQuery("");
    await refreshCallData("");
  }

  const statCards = useMemo(() => [
    ["Total calls", stats?.total_calls ?? 0, "All recorded sessions"],
    ["Active now", stats?.active_calls ?? 0, (stats?.active_calls ?? 0) ? "Live status syncing" : "No calls in progress"],
    ["Completed", stats?.completed_calls ?? 0, "Successfully ended"],
    ["Failed / missed", stats?.failed_calls ?? 0, "Needs review"],
    ["Interested leads", stats?.interested_leads ?? 0, "Qualified interest"],
    ["Follow-ups", stats?.follow_ups_required ?? 0, "Action required"],
    ["Avg. duration", formatDuration(stats?.average_call_duration_seconds ?? 0), "Across completed calls"],
  ], [stats]);

  const realReady = Boolean(telephony?.real_call_ready);
  const trialBootstrap = telephony?.twilio_account_tier === "trial";

  return <>
    <header className="header dashboardHeader">
      <div>
        <div className="eyebrow">VOICE AUTOMATION CONSOLE</div>
        <h1>AI Calling Agent</h1>
        <p>Launch outbound calls, monitor conversations, and review AI-qualified outcomes in real time.</p>
      </div>
      <div className="headerActions">
        <button className="btn ghost refreshBtn" onClick={() => refreshCallData()} disabled={refreshing}>{refreshing ? "↻ Syncing…" : "↻ Refresh"}</button>
        <span className={`badge ${realReady ? "green" : "amber"}`}><span className="statusDot" />{realReady ? (trialBootstrap ? "Twilio trial ready" : "Real calling ready") : "Browser demo ready"}</span>
      </div>
    </header>

    {error && <div className="error" role="alert"><strong>Action needed:</strong> {error}</div>}

    <section className={`providerBanner ${realReady ? "ready" : "warning"}`}>
      <div className="providerIcon">{realReady ? "☎" : "◌"}</div>
      <div className="providerCopy">
        <strong>{realReady ? "Real phone calling is configured" : "Real phone calling needs Twilio configuration"}</strong>
        <span>{realReady ? (trialBootstrap ? "Trial-safe Twilio calling is enabled. The destination phone handles the conversation while this dashboard tracks status and transcript." : "Twilio rings the customer’s phone while this dashboard tracks lifecycle, transcript, and outcome.") : "The browser voice demo is available now. Configure Twilio credentials and a public backend callback URL for real calls."}</span>
      </div>
      <div className="providerPills"><span className="badge">AI · OpenRouter</span><span className="badge">Voice · Twilio</span><span className="badge">Fallback · Browser</span></div>
    </section>

    <section className="stats">
      {statCards.map(([label, value, hint], index) => <div className="stat" key={String(label)} style={{animationDelay:`${index * 45}ms`}}><div className="label">{label}</div><div className="value">{value}</div><div className="statHint">{hint}</div></div>)}
    </section>

    <section className="grid2" id="campaign">
      <div className="card liftCard">
        <div className="cardHead"><div><h2>Create calling campaign</h2><span>Add a contact and launch an AI-assisted outbound call.</span></div><span className="badge blue">New call</span></div>
        <div className="cardBody">
          <form className="formGrid" onSubmit={submitCustomer}>
            <div className="field"><label>Customer name *</label><input className="input" value={form.name} onChange={e=>setForm(prev=>({...prev,name:e.currentTarget.value}))} placeholder="Rahul Kumar" required /></div>
            <div className="field"><label>Phone number *</label><input className="input" type="tel" inputMode="tel" autoComplete="tel" value={form.phone_number} onChange={e=>setForm(prev=>({...prev,phone_number:e.currentTarget.value}))} placeholder="+91 98765 43210" required /><small className="hint">Indian 10-digit numbers are normalized to +91 automatically.</small></div>
            <div className="field"><label>Company / hotel</label><input className="input" value={form.company_name} onChange={e=>setForm(prev=>({...prev,company_name:e.currentTarget.value}))} placeholder="Grand Residency" /></div>
            <div className="field"><label>Purpose</label><input className="input" value={form.purpose} onChange={e=>setForm(prev=>({...prev,purpose:e.currentTarget.value}))} /></div>
            <div className="field full"><label>Product / service</label><input className="input" value={form.product} onChange={e=>setForm(prev=>({...prev,product:e.currentTarget.value}))} /></div>
            <div className="field full"><button className="btn primary wideBtn" disabled={busy}>{busy ? "Working…" : "＋ Add customer"}</button></div>
          </form>
        </div>
      </div>

      <div className="card liftCard">
        <div className="cardHead"><div><h2>Customers</h2><span>Start a real Twilio call or use the browser voice demo.</span></div><span className="countPill">{customers.length} contacts</span></div>
        <div className="cardBody customerList">
          {customers.length === 0 && <div className="empty"><div className="emptyIcon">◎</div>No customers yet. Add your first contact.</div>}
          {customers.map(c => <div className="customerRow" key={c.id}>
            <div className="contactAvatar">{c.name.slice(0,1).toUpperCase()}</div>
            <div className="customerIdentity"><strong>{c.name}</strong><small>{c.phone_number}{c.company_name ? ` · ${c.company_name}` : ""}</small></div>
            <div className="customerActions">
              <button className="btn callReal" disabled={busy || !realReady} title={realReady ? "Ring the customer's actual phone through Twilio" : (telephony?.reasons?.join("; ") || "Configure Twilio first")} onClick={()=>startCall(c.id,"twilio")}>☎ Call phone</button>
              <button className="btn ghost" disabled={busy} onClick={()=>startCall(c.id,"browser")}>🎙 Browser demo</button>
            </div>
          </div>)}
          {!realReady && telephony && <div className="setupNote"><strong>Real-call setup</strong>{telephony.reasons.map(r=><span key={r}>• {r}</span>)}</div>}
        </div>
      </div>
    </section>

    <section className="card" id="calls">
      <div className="cardHead historyHead">
        <div><h2>Call history</h2><span>Live calls auto-sync every 3 seconds{lastUpdated ? ` · Last sync ${lastUpdated.toLocaleTimeString()}` : ""}.</span></div>
        <div className="filters">
          <input className="input" placeholder="Customer" aria-label="Filter by customer" value={filters.customer} onChange={e=>setFilters({...filters,customer:e.target.value})}/>
          <select className="select" aria-label="Filter by status" value={filters.status} onChange={e=>setFilters({...filters,status:e.target.value})}><option value="">All statuses</option><option value="queued">Queued</option><option value="ringing">Ringing</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="failed">Failed</option><option value="no_answer">No answer</option><option value="no_response">No response</option><option value="disconnected">Disconnected</option></select>
          <select className="select" aria-label="Filter by lead status" value={filters.lead_status} onChange={e=>setFilters({...filters,lead_status:e.target.value})}><option value="">All leads</option><option value="Interested">Interested</option><option value="Needs follow-up">Needs follow-up</option><option value="Not interested">Not interested</option></select>
          <select className="select" aria-label="Filter by follow-up" value={filters.follow_up_required} onChange={e=>setFilters({...filters,follow_up_required:e.target.value})}><option value="">Follow-up: all</option><option value="true">Required</option><option value="false">Not required</option></select>
          <input className="input" placeholder="Outcome" aria-label="Filter by outcome" value={filters.outcome} onChange={e=>setFilters({...filters,outcome:e.target.value})}/>
          <input className="input" type="date" aria-label="Filter by date" value={filters.date} onChange={e=>setFilters({...filters,date:e.target.value})}/>
          <button className="btn secondary" onClick={applyFilters}>Apply</button>
          <button className="btn ghost" onClick={resetFilters}>Reset</button>
        </div>
      </div>
      <div className="tableWrap">
        <table><thead><tr><th>Customer</th><th>Phone number</th><th>Date</th><th>Duration</th><th>Status</th><th>Outcome</th><th>Follow-up</th><th></th></tr></thead>
        <tbody>{calls.map(call => <tr key={call.id} className={isCallLive(call) ? "liveRow" : ""}>
          <td><div className="tableCustomer"><span className="miniAvatar">{call.customer_name.slice(0,1).toUpperCase()}</span><strong>{call.customer_name}</strong></div></td>
          <td>{call.phone_number}</td><td>{new Date(call.created_at).toLocaleString()}</td><td>{formatDuration(call.duration_seconds)}</td><td>{statusBadge(call)}</td><td>{call.outcome || (isCallLive(call) ? "In progress" : "—")}</td><td>{call.follow_up_required ? <span className="badge amber">Required</span> : <span className="mutedText">—</span>}</td><td><Link className="btn ghost compactBtn" href={`/calls/${call.id}`}>View →</Link></td>
        </tr>)}</tbody></table>
        {calls.length === 0 && <div className="empty"><div className="emptyIcon">⌁</div>No calls match the current filters.</div>}
      </div>
    </section>
  </>;
}
