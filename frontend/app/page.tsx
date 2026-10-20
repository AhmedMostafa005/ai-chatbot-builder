'use client';
import { useCallback, useEffect, useState } from 'react';

type Bot = { id: string; name: string; model: string; published: boolean; primary_color: string };
type ChatLine = { role: 'user' | 'assistant'; content: string; sources?: string[] };

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
const UPLOAD_INPUT = { padding: 10, fontSize: 13 } as const;

export default function Home() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [name, setName] = useState('');
  const [tenant, setTenant] = useState('demo-client');
  const [pw, setPw] = useState('');
  const [error, setError] = useState('');
  const [uploadStatus, setUploadStatus] = useState<Record<string, string>>({});
  const [chatLogs, setChatLogs] = useState<Record<string, ChatLine[]>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const APIHeaders = useCallback(() => ({ 'X-Tenant-ID': tenant, ...(pw ? { 'X-Dashboard-Password': pw } : {}) }), [tenant, pw]);

  async function load() {
    try {
      const r = await fetch(`${API}/api/bots`, { headers: APIHeaders(), cache: 'no-store' });
      if (!r.ok) throw new Error(await r.text());
      setBots(await r.json());
      setError('');
    } catch (e) { setError(String(e)); }
  }
  useEffect(() => { setPw(localStorage.getItem('chatbuilder_pw') || ''); }, []);
  useEffect(() => { load(); }, [pw, tenant]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      const r = await fetch(`${API}/api/bots`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...APIHeaders() }, body: JSON.stringify({ name }) });
      if (!r.ok) throw new Error(await r.text());
      setName('');
      await load();
    } catch (e) { setError(String(e)); }
  }

  async function publish(bot: Bot) {
    try {
      const r = await fetch(`${API}/api/bots/${bot.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...APIHeaders() }, body: JSON.stringify({ published: !bot.published }) });
      if (!r.ok) throw new Error(await r.text());
      await load();
    } catch (e) { setError(String(e)); }
  }

  async function upload(bot: Bot, file: File) {
    setUploadStatus(s => ({ ...s, [bot.id]: `Uploading "${file.name}" — extracting, chunking, embedding...` }));
    const form = new FormData();
    form.append('file', file);
    try {
      const r = await fetch(`${API}/api/bots/${bot.id}/documents`, { method: 'POST', headers: APIHeaders(), body: form });
      if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail || 'Upload failed');
      const data = await r.json();
      setUploadStatus(s => ({ ...s, [bot.id]: `✓ ${file.name}: ${data.chunks_created} chunks indexed` }));
      setTimeout(() => setUploadStatus(s => ({ ...s, [bot.id]: '' })), 8000);
    } catch (e) {
      setUploadStatus(s => ({ ...s, [bot.id]: `✗ ${e}` }));
    }
  }

  async function send(bot: Bot) {
    const draft = (drafts[bot.id] || '').trim();
    if (!draft) return;
    const log = chatLogs[bot.id] || [];
    setChatLogs(l => ({ ...l, [bot.id]: [...log, { role: 'user', content: draft }, { role: 'assistant', content: '' }] }));
    setDrafts(d => ({ ...d, [bot.id]: '' }));
    const replaceLast = (line: ChatLine) => {
      setChatLogs(l => {
        const arr = [...(l[bot.id] || [])];
        arr[arr.length - 1] = line;
        return { ...l, [bot.id]: arr };
      });
    };
    try {
      const r = await fetch(`${API}/api/chat/stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: bot.id, visitor_id: 'dashboard-test', message: draft }) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail || 'Chat failed');
      const reader = r.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '', answer = '', sources: string[] = [];
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 1);
          if (!line) continue;
          let msg;
          try { msg = JSON.parse(line); } catch { continue; }
          if (typeof msg.delta === 'string') { answer += msg.delta; replaceLast({ role: 'assistant', content: answer, sources }); }
          if (Array.isArray(msg.sources)) { sources = msg.sources; replaceLast({ role: 'assistant', content: answer, sources }); }
        }
      }
      if (!answer) replaceLast({ role: 'assistant', content: 'I could not generate a response.' });
    } catch (e) {
      replaceLast({ role: 'assistant', content: `Error: ${e}` });
    }
  }

  return <main style={{ maxWidth: 1000, margin: '0 auto', padding: 32 }}>
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
      <div>
        <p style={{ color: '#2563eb', fontWeight: 700 }}>AI CHATBOT BUILDER</p>
        <h1 style={{ margin: '8px 0' }}>Dashboard</h1>
        <p style={{ color: '#64748b' }}>Create bots, upload knowledge, test chats — all from here.</p>
      </div>
      <label>Development tenant<br /><input value={tenant} onChange={e => setTenant(e.target.value)} style={{ padding: 10, border: '1px solid #cbd5e1', borderRadius: 8 }} /></label>
      <label>Dashboard password<br />
        <input type="password" value={pw || ''} onChange={e => { setPw(e.target.value); localStorage.setItem('chatbuilder_pw', e.target.value); }} placeholder="Set once, saved in this browser" style={{ padding: 10, border: '1px solid #cbd5e1', borderRadius: 8 }} />
      </label>
    </header>

    <form onSubmit={create} style={{ display: 'flex', gap: 10, margin: '28px 0', padding: 18, background: 'white', border: '1px solid #e2e8f0', borderRadius: 14 }}>
      <input required value={name} onChange={e => setName(e.target.value)} placeholder="New chatbot name" style={{ flex: 1, minWidth: 0, padding: 12, border: '1px solid #cbd5e1', borderRadius: 8 }} />
      <button style={{ background: '#2563eb', color: 'white', border: 0, borderRadius: 8, padding: '0 18px', fontWeight: 600 }}>Create chatbot</button>
    </form>

    {error && <pre style={{ whiteSpace: 'pre-wrap', color: '#b91c1c' }}>{error}</pre>}

    <h2>Your chatbots ({bots.length})</h2>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14 }}>
      {bots.map(b => (
        <article key={b.id} style={{ background: 'white', padding: 20, border: '1px solid #e2e8f0', borderRadius: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <h3 style={{ marginTop: 0 }}>{b.name}</h3>
            <span style={{ color: b.published ? '#047857' : '#64748b' }}>{b.published ? 'Published' : 'Draft'}</span>
          </div>
          <p style={{ color: '#64748b', fontSize: 13 }}>Model: {b.model}</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={() => publish(b)} style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid #cbd5e1', background: 'white', cursor: 'pointer' }}>{b.published ? 'Unpublish' : 'Publish'}</button>
          </div>

          <details style={{ marginTop: 14 }}><summary>Embed code</summary>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{`<script src="${API}/widget.js" data-bot-id="${b.id}" data-api-base="${API}"></script>`}</pre>
            <a href={API} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>API</a>
          </details>

          <p style={{ fontSize: 13, fontWeight: 600, marginTop: 14, marginBottom: 4 }}>📄 Knowledge</p>
          <input type="file" accept=".txt,.md,.pdf,.docx,.csv,.json,.html,.htm" onChange={e => { const f = e.target.files?.[0]; if (f) upload(b, f); }} style={UPLOAD_INPUT} />
          {uploadStatus[b.id] && <p style={{ fontSize: 12, color: uploadStatus[b.id].startsWith('✓') ? '#047857' : uploadStatus[b.id].startsWith('✗') ? '#b91c1c' : '#64748b' }}>{uploadStatus[b.id]}</p>}

          <p style={{ fontSize: 13, fontWeight: 600, marginTop: 14, marginBottom: 4 }}>💬 Test chat {!b.published && <span style={{ color: '#b45309', fontWeight: 400 }}>(publish first)</span>}</p>
          <div style={{ maxHeight: 240, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 8, padding: 10, marginBottom: 8 }}>
            <div style={{ color: '#9ca3af', fontSize: 12 }}>Answers use uploaded knowledge + Gemini.</div>
            {(chatLogs[b.id] || []).map((m, i) => (
              <div key={i} style={{ marginTop: 8, fontSize: 14 }}>
                <b style={{ color: m.role === 'user' ? '#2563eb' : '#047857' }}>{m.role === 'user' ? 'You: ' : 'Bot: '}</b>
                {m.content}
                {m.sources && m.sources.length > 0 && <div style={{ fontSize: 10, color: '#94a3b8' }}>Sources: {m.sources.join(' | ')}</div>}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input value={drafts[b.id] || ''} onChange={e => setDrafts(d => ({ ...d, [b.id]: e.target.value }))} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(b); } }} placeholder={b.published ? 'Ask the bot something...' : 'Publish this bot to test it'} disabled={!b.published} style={{ flex: 1, minWidth: 0, padding: 10, border: '1px solid #cbd5e1', borderRadius: 8 }} />
            <button onClick={() => send(b)} disabled={!b.published} style={{ background: '#2563eb', color: 'white', border: 0, borderRadius: 8, padding: '0 14px', fontWeight: 600, cursor: 'pointer' }}>Send</button>
          </div>
        </article>
      ))}
    </div>
  </main>;
}
