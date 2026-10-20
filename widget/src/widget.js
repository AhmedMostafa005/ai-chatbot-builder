(() => {
  const script = document.currentScript;
  const botId = script?.dataset.botId;
  const apiBase = (script?.dataset.apiBase || new URL(script.src).origin).replace(/\/$/, '');
  if (!botId) { console.error('ChatBuilder widget: data-bot-id is required'); return; }
  const visitorKey = `chatbuilder_visitor_${botId}`;
  let visitorId = localStorage.getItem(visitorKey);
  if (!visitorId) { visitorId = (crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`); localStorage.setItem(visitorKey, visitorId); }
  const root = document.createElement('div');
  root.id = 'chatbuilder-chat-root';
  root.attachShadow({ mode: 'open' });
  document.body.appendChild(root);
  root.shadowRoot.innerHTML = `
    <style>
      :host{font-family:system-ui,-apple-system,sans-serif;color:#172033}*{box-sizing:border-box}
      .bubble{position:fixed;z-index:2147483000;right:22px;bottom:22px;width:58px;height:58px;border:0;border-radius:50%;background:#2563eb;color:white;font-size:25px;cursor:pointer;box-shadow:0 5px 22px #0003}
      .panel{position:fixed;z-index:2147483000;right:22px;bottom:92px;width:min(360px,calc(100vw - 28px));height:min(520px,calc(100vh - 125px));background:white;border:1px solid #e5e7eb;border-radius:16px;box-shadow:0 10px 40px #0003;display:none;overflow:hidden;direction:auto}
      .head{padding:14px 16px;background:#2563eb;color:white;font-weight:650;display:flex;justify-content:space-between}.close{border:0;background:transparent;color:white;font-size:20px;cursor:pointer}
      .messages{height:calc(100% - 118px);overflow:auto;padding:12px;background:#f8fafc}.msg{padding:9px 11px;border-radius:12px;margin:8px 0;max-width:88%;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.4;font-size:14px}.bot{background:white;border:1px solid #e5e7eb;margin-right:auto}.user{background:#dbeafe;margin-left:auto}
      form{display:flex;gap:7px;padding:10px;border-top:1px solid #e5e7eb}input{flex:1;min-width:0;border:1px solid #cbd5e1;border-radius:10px;padding:10px;font:inherit}form button{border:0;border-radius:10px;padding:0 13px;background:#2563eb;color:white;cursor:pointer}
    </style>
    <button class="bubble" aria-label="Open chat">✦</button>
    <section class="panel" role="dialog" aria-label="Chat assistant"><div class="head"><span>Chat with us</span><button class="close" aria-label="Close">×</button></div><div class="messages" aria-live="polite"></div><form><input aria-label="Message" placeholder="Type your message…" required maxlength="10000"><button type="submit">Send</button></form></section>`;
  const $ = (s) => root.shadowRoot.querySelector(s);
  const panel = $('.panel'), list = $('.messages'), input = $('input');
  const add = (text, who) => { const el = document.createElement('div'); el.className = `msg ${who}`; el.textContent = text; list.appendChild(el); list.scrollTop = list.scrollHeight; return el; };
  $('.bubble').onclick = () => { panel.style.display = 'block'; input.focus(); };
  $('.close').onclick = () => { panel.style.display = 'none'; };
  add('Hello! How can I help?', 'bot');
  $('form').addEventListener('submit', async (e) => {
    e.preventDefault(); const message = input.value.trim(); if (!message) return;
    add(message, 'user'); input.value = ''; const pending = add('Thinking…', 'bot');
    try {
      const res = await fetch(`${apiBase}/api/chat/stream`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({bot_id:botId, visitor_id:visitorId, message}) });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'Request failed'); }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '', answer = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, idx).trim(); buffer = buffer.slice(idx + 1);
          if (!line) continue;
          let msg; try { msg = JSON.parse(line); } catch { continue; }
          if (typeof msg.delta === 'string') { answer += msg.delta; pending.textContent = answer; }
        }
      }
      if (!answer) pending.textContent = 'I could not generate a response.';
      // Text-only rendering avoids injecting model output as HTML.
    } catch (err) { pending.textContent = `Sorry, there was a problem: ${err.message}`; }
  });
})();
