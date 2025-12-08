document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const historyList = document.getElementById('history-list');
    const newChatBtn = document.getElementById('new-chat-btn');

    let currentConversationId = null;

    // Client-side storage key
    const STORAGE_KEY = 'webcloud.conversations';

    // Simple UUID generator (not cryptographically strong)
    function uuidv4() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    function readStore() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return {};
            const parsed = JSON.parse(raw);
            return typeof parsed === 'object' && parsed ? parsed : {};
        } catch (_) {
            return {};
        }
    }

    function writeStore(obj) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
        } catch (_) {}
    }

    function getConversation(id) {
        const store = readStore();
        return store[id] || null;
    }

    function upsertConversation(conv) {
        const store = readStore();
        store[conv.id] = conv;
        writeStore(store);
    }

    function listConversations() {
        const store = readStore();
        return Object.values(store)
            .map(c => ({ id: c.id, title: c.title || 'New Chat', updated_at: c.updated_at || '' }))
            .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));
    }

    // Auto-resize textarea
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value === '') {
            this.style.height = '24px'; // Reset to min-height
        }
    });
    
    // --- 核心修改部分开始 ---
    // Render markdown + code highlighting + KaTeX safely into an element
    function renderMarkdownToElement(el, markdownText) {
        if (!markdownText) {
            el.innerHTML = '';
            return;
        }

        if (typeof marked === 'undefined') {
            el.textContent = markdownText;
            return;
        }

        // 1. 保护公式
        // 使用 Map 存储公式，防止 marked 解析破坏
        const mathMap = new Map();
        let mathCounter = 0;

        // 【关键修改点】生成不含下划线的 Key，避免被 marked 解析为斜体
        const makeKey = () => `KATEXMATHBLOCK${mathCounter++}`;

        const replaceMath = (regex) => {
            markdownText = markdownText.replace(regex, (match) => {
                const key = makeKey(); 
                mathMap.set(key, match);
                return key;
            });
        };

        // 保护顺序：先块级，后行内
        replaceMath(/\$\$([\s\S]+?)\$\$/g);     // $$ ... $$
        replaceMath(/\\\[([\s\S]+?)\\\]/g);     // \[ ... \]
        replaceMath(/\\\(([\s\S]+?)\\\)/g);     // \( ... \)
        replaceMath(/\$([^$\n]+?)\$/g);         // $ ... $

        // 2. 配置 Marked
        marked.setOptions({
            gfm: true,
            breaks: true,
            headerIds: false,
            mangle: false
        });

        // 3. 解析 Markdown
        let htmlContent = marked.parse(markdownText);

        // 4. 还原公式
        // 这时 htmlContent 里只有 "KATEXMATHBLOCK0"，marked 不会动它
        mathMap.forEach((value, key) => {
            // 使用 split/join 替换比 replace 更安全，防止 key 在文本中出现多次（虽然这里 key 是唯一的）
            htmlContent = htmlContent.split(key).join(value);
        });

        // 5. 净化 HTML (如果需要)
        if (typeof DOMPurify !== 'undefined') {
            htmlContent = DOMPurify.sanitize(htmlContent, {
                ADD_TAGS: ['span', 'code', 'pre'],
                ADD_ATTR: ['class', 'style']
            });
        }

        // 6. 插入 DOM
        el.innerHTML = htmlContent;

        // 7. 代码高亮
        try { 
            if (typeof hljs !== 'undefined') {
                el.querySelectorAll('pre code').forEach((block) => {
                    hljs.highlightElement(block);
                });
            } 
        } catch (e) {}

        // 8. 渲染公式 (KaTeX)
        try {
            if (typeof renderMathInElement !== 'undefined') {
                renderMathInElement(el, {
                    delimiters: [
                        {left: "$$", right: "$$", display: true},
                        {left: "\\[", right: "\\]", display: true},
                        {left: "$", right: "$", display: false},
                        {left: "\\(", right: "\\)", display: false}
                    ],
                    throwOnError: false
                });
            }
        } catch (e) {}
    }
    // --- 核心修改部分结束 ---

    function appendMessage(role, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        
        const wrapperDiv = document.createElement('div');
        wrapperDiv.className = 'message-wrapper';

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar';
        avatarDiv.textContent = role === 'user' ? 'U' : 'AI';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';

        // Render assistant text as Markdown (with highlighting and KaTeX)
        if (role === 'assistant') {
            renderMarkdownToElement(contentDiv, text);
        } else {
            // user or other roles: plain text
            // 对于用户的输入，如果你也想支持公式，可以改为调用 renderMarkdownToElement
            contentDiv.textContent = text; 
        }
        
        wrapperDiv.appendChild(avatarDiv);
        wrapperDiv.appendChild(contentDiv);
        msgDiv.appendChild(wrapperDiv);
        
        chatContainer.appendChild(msgDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function showLoading() {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant loading';
        msgDiv.id = 'loading-message';
        
        const wrapperDiv = document.createElement('div');
        wrapperDiv.className = 'message-wrapper';

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar';
        avatarDiv.textContent = 'AI';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        contentDiv.innerHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        
        wrapperDiv.appendChild(avatarDiv);
        wrapperDiv.appendChild(contentDiv);
        msgDiv.appendChild(wrapperDiv);
        
        chatContainer.appendChild(msgDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return msgDiv;
    }

    function clearChat() {
        chatContainer.innerHTML = '';
        // Add welcome message
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant';
        msgDiv.innerHTML = `
            <div class="message-wrapper">
                <div class="avatar">AI</div>
                <div class="content"></div>
            </div>
        `;
        // Render welcome message through markdown renderer
        const welcomeContent = msgDiv.querySelector('.content');
        renderMarkdownToElement(welcomeContent, '你好！我是你的 AI 助手，有什么可以帮你的吗？');
        chatContainer.appendChild(msgDiv);
    }

    async function loadConversations() {
        const conversations = listConversations();
        historyList.innerHTML = '';
        conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'history-item';
            if (conv.id === currentConversationId) {
                item.classList.add('active');
            }
            item.innerHTML = `
                <svg stroke="currentColor" fill="none" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" height="16" width="16" xmlns="http://www.w3.org/2000/svg"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                ${conv.title}
            `;
            item.addEventListener('click', () => loadConversation(conv.id));
            historyList.appendChild(item);
        });
    }

    async function loadConversation(id) {
        if (currentConversationId === id) return;
        const conv = getConversation(id);
        if (!conv) return;
        currentConversationId = id;
        chatContainer.innerHTML = '';
        conv.messages.forEach(msg => appendMessage(msg.role, msg.content));
        loadConversations();
    }

    function startNewChat() {
        currentConversationId = null;
        clearChat();
        loadConversations();
    }

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;

        appendMessage('user', text);
        userInput.value = '';
        userInput.style.height = '24px';

        const loadingMsg = showLoading();

        // Ensure conversation exists locally and update local store with user msg
        let conv = currentConversationId ? getConversation(currentConversationId) : null;
        if (!conv) {
            const newId = uuidv4();
            conv = {
                id: newId,
                title: text.length > 30 ? text.slice(0, 30) + '...' : text,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                messages: []
            };
            currentConversationId = newId;
        }
        conv.messages.push({ role: 'user', content: text });
        conv.updated_at = new Date().toISOString();
        upsertConversation(conv);
        loadConversations();

        // Build full history to send (including the new user message)
        const historyToSend = conv.messages.map(m => ({ role: m.role, content: m.content }));

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: currentConversationId,
                    messages: historyToSend
                })
            });

            const data = await response.json();

            if (loadingMsg && loadingMsg.parentNode) {
                loadingMsg.parentNode.removeChild(loadingMsg);
            }

            if (response.ok) {
                appendMessage('assistant', data.response);
                // Save assistant reply locally
                const updated = getConversation(currentConversationId) || conv;
                updated.messages.push({ role: 'assistant', content: data.response });
                updated.updated_at = new Date().toISOString();
                upsertConversation(updated);
                loadConversations();
            } else {
                appendMessage('assistant', `Error: ${data.error}`);
            }
        } catch (error) {
            if (loadingMsg && loadingMsg.parentNode) {
                loadingMsg.parentNode.removeChild(loadingMsg);
            }
            appendMessage('assistant', `Error: ${error.message}`);
        }
    }

    // Event Listeners
    newChatBtn.addEventListener('click', startNewChat);
    sendBtn.addEventListener('click', sendMessage);
    // Keyboard behavior:
    // - Enter: newline (default)
    // - Ctrl+Enter: send message
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Initial load
    loadConversations();
});