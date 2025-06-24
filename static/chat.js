document.addEventListener('DOMContentLoaded', () => {
    console.log('chat.js loaded');


    const toggleBtn = document.getElementById('chat-toggle');
    const sidebar = document.getElementById('chat-sidebar');
    const closeBtn = document.getElementById('chat-close');
    const userList = document.getElementById('chat-user-list');
    const convView = document.getElementById('chat-conversation');
    const backBtn = document.getElementById('back-to-users');
    const convWith = document.getElementById('conv-with');
    const convMsgs = document.getElementById('conv-messages');
    const convText = document.getElementById('conv-text');
    const convSend = document.getElementById('conv-send');

    const missing = [];
    [
        ['toggleBtn', toggleBtn],
        ['sidebar', sidebar],
        ['closeBtn', closeBtn],
        ['userList', userList],
        ['convView', convView],
        ['backBtn', backBtn],
        ['convWith', convWith],
        ['convMsgs', convMsgs],
        ['convText', convText],
        ['convSend', convSend]
    ].forEach(([name, el]) => {
        if (!el) missing.push(name);
    });
    if (missing.length) {
        console.error('Chat.js: Missing elements:', missing.join(', '));
        return;
    }

    const USERS_URL = '/chat/users';
    const MESSAGES_URL = otherId => `/chat/messages/${otherId}`;

    let currentOther = null;
    let poller = null;

    toggleBtn.addEventListener('click', () => {
        console.log('toggle clicked');
        sidebar.classList.toggle('open');
        if (sidebar.classList.contains('open')) {
            showUserList();
            loadUserList();
        }
    });

    closeBtn.addEventListener('click', () => {
        console.log('close clicked');
        sidebar.classList.remove('open');
    });

    backBtn.addEventListener('click', () => {
        console.log('back clicked');
        convView.classList.add('d-none');
        userList.classList.remove('d-none');
        clearInterval(poller);
        poller = null;
    });

    async function loadUserList() {
        userList.innerHTML = '<div class="text-center text-muted">Loading users…</div>';
        try {
            const res = await fetch(USERS_URL, { credentials: 'same-origin' });
            console.log('GET', USERS_URL, '→', res.status);
            if (res.status === 401) {
                userList.innerHTML = '<div class="text-danger text-center p-2">Please log in to chat.</div>';
                return;
            }
            if (!res.ok) throw new Error(res.statusText);
            const users = await res.json();
            if (!Array.isArray(users) || users.length === 0) {
                userList.innerHTML = '<div class="text-center text-muted">No other users.</div>';
                return;
            }
            userList.innerHTML = users.map(u => `
        <div class="list-group-item list-group-item-action"
             data-id="${u.id}" data-name="${u.username}">
          <strong>${u.username}</strong>
          <small class="text-muted">(${u.role})</small>
        </div>
      `).join('');
            userList.querySelectorAll('.list-group-item').forEach(el => {
                el.addEventListener('click', () => startConversation(el.dataset.id, el.dataset.name));
            });
        } catch (err) {
            console.error('Error loading users:', err);
            userList.innerHTML = `<div class="text-danger text-center p-2">Error: ${err.message}</div>`;
        }
    }


    function showUserList() {
        convView.classList.add('d-none');
        userList.classList.remove('d-none');
    }


    function startConversation(otherId, otherName) {
        console.log('Start conversation with', otherId, otherName);
        currentOther = otherId;
        convWith.textContent = otherName;
        userList.classList.add('d-none');
        convView.classList.remove('d-none');
        convMsgs.innerHTML = '<div class="text-center text-muted">Loading messages…</div>';
        fetchMessages();
        if (poller) clearInterval(poller);
        poller = setInterval(fetchMessages, 2000);
    }


    async function fetchMessages() {
        if (!currentOther) return;
        try {
            const url = MESSAGES_URL(currentOther);
            const res = await fetch(url, { credentials: 'same-origin' });
            console.log('GET', url, '→', res.status);
            if (!res.ok) throw new Error(res.statusText);
            const msgs = await res.json();
            convMsgs.innerHTML = msgs.map(m => {
                const align = m.from === sessionUserId ? 'text-end' : 'text-start';
                return `<div class="${align} mb-2">
                  <span class="badge bg-secondary">${m.text}</span>
                </div>`;
            }).join('');
            convMsgs.scrollTop = convMsgs.scrollHeight;
        } catch (err) {
            console.error('Error fetching messages:', err);
        }
    }


    async function sendMessage() {
        if (!currentOther) return;
        const text = convText.value.trim();
        if (!text) {
            console.log('Empty message, skipping send');
            return;
        }
        try {
            const url = MESSAGES_URL(currentOther);
            const res = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
            console.log('POST', url, '→', res.status);
            if (res.status === 401) {
                console.error('Not authenticated');
                return;
            }
            if (!res.ok) throw new Error(res.statusText);
            convText.value = '';
            fetchMessages();
        } catch (err) {
            console.error('Error sending message:', err);
        }
    }


    convSend.addEventListener('click', sendMessage);
    convText.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }

    });
});