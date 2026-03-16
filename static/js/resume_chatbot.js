/* Lightweight Resume Chatbot UI and client */
(function () {

  function createElement(tag, attrs = {}, html = '') {
    const el = document.createElement(tag);
    Object.keys(attrs).forEach(k => el.setAttribute(k, attrs[k]));
    el.innerHTML = html;
    return el;
  }

  const container = createElement('div', {
    id: 'miniResumeChat',
    style: 'position:fixed;right:20px;bottom:20px;z-index:2000'
  });

  const button = createElement('button', {
    id: 'miniChatToggle',
    class: 'btn btn-primary',
    style: 'border-radius:50%;width:56px;height:56px;font-size:20px'
  }, '💬');

  const panel = createElement('div', {
    id: 'miniChatPanel',
    style: 'display:none;min-width:320px;max-width:420px;background:#0f172a;color:#fff;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,0.3);overflow:hidden;margin-bottom:8px'
  });

  panel.innerHTML = `
    <div style="padding:12px;border-bottom:1px solid rgba(255,255,255,0.03);background:linear-gradient(90deg,#111827,#0b1220)">
      <strong>Resume Assistant</strong>
      <button id="miniChatClose" style="float:right;background:none;border:none;color:#fff;font-size:16px">✕</button>
      <div style="font-size:12px;opacity:0.8">Ask anything about resumes, careers, or general questions</div>
    </div>

    <div id="miniChatBody" style="padding:12px;max-height:260px;overflow:auto;background:#071022"></div>

    <div style="padding:10px;background:#020617;display:flex;gap:8px;align-items:center">
      <input id="miniChatInput" placeholder="Type a message..." 
      style="flex:1;padding:8px;border-radius:6px;border:1px solid rgba(255,255,255,0.06);background:transparent;color:#fff">

      <button id="miniChatSend" class="btn btn-sm btn-light">Send</button>
    </div>
  `;

  container.appendChild(panel);
  container.appendChild(button);
  document.body.appendChild(container);

  const toggle = document.getElementById('miniChatToggle');
  const close = document.getElementById('miniChatClose');
  const body = document.getElementById('miniChatBody');
  const input = document.getElementById('miniChatInput');
  const send = document.getElementById('miniChatSend');

  function openPanel() {
    panel.style.display = 'block';
    toggle.style.display = 'none';
    input.focus();
  }

  function closePanel() {
    panel.style.display = 'none';
    toggle.style.display = 'inline-block';
  }

  toggle.addEventListener('click', openPanel);
  close.addEventListener('click', closePanel);

  function escapeHtml(str) {
    return String(str).replace(/[&<>"]/g, s => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;'
    })[s]);
  }

  function addMessage(who, text) {
    const d = document.createElement('div');
    d.style.marginBottom = '10px';

    const safe = escapeHtml(text).replace(/\n/g, '<br>');

    if (who === 'user') {
      d.innerHTML = `
        <div style="text-align:right">
          <small style="opacity:0.7">You</small>
          <div style="display:inline-block;background:#0ea5a4;color:#002;padding:8px;border-radius:6px;margin-top:4px">
            ${safe}
          </div>
        </div>
      `;
    } else {
      d.innerHTML = `
        <div>
          <small style="opacity:0.7">Assistant</small>
          <div style="display:inline-block;background:#111827;color:#fff;padding:8px;border-radius:6px;margin-top:4px">
            ${safe}
          </div>
        </div>
      `;
    }

    body.appendChild(d);
    body.scrollTop = body.scrollHeight;
  }

  function showTyping() {
    const typing = document.createElement('div');
    typing.id = "typingIndicator";
    typing.innerHTML = `<small style="opacity:0.6">Assistant is typing...</small>`;
    typing.style.marginBottom = '8px';
    body.appendChild(typing);
    body.scrollTop = body.scrollHeight;
  }

  function removeTyping() {
    const t = document.getElementById("typingIndicator");
    if (t) t.remove();
  }

  async function sendMessage() {

    const txt = input.value.trim();
    if (!txt) return;

    addMessage('user', txt);
    input.value = '';

    showTyping();
    send.disabled = true;

    let resumeText = '';

    try {
      const f = document.querySelector('form');

      if (f) {
        const fm = new FormData(f);

        for (const [k, v] of fm.entries()) {
          if (['summary', 'experience', 'education', 'skills', 'achievements'].includes(k)) {
            resumeText += '\n' + v;
          }
        }
      }

    } catch (e) { }

    const context =
      location.pathname.includes('/builder') ? 'builder' :
        location.pathname.includes('/analyzer') ? 'analyzer' :
          'general';

    let csrfToken = '';
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    if (csrfInput) csrfToken = csrfInput.value;

    try {

      const res = await fetch('/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          message: txt,
          context: context,
          resume: resumeText
        })
      });

      const json = await res.json();

      removeTyping();
      send.disabled = false;

      if (res.ok && json.response) {
        addMessage('bot', json.response);
      } else {
        addMessage('bot', 'Sorry, I could not process that request.');
      }

    } catch (err) {

      removeTyping();
      send.disabled = false;

      addMessage('bot', 'Network error: could not reach the server.');
    }
  }

  send.addEventListener('click', sendMessage);

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendMessage();
    }
  });

})();