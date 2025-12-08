document.addEventListener('DOMContentLoaded', () => {
    const apiKeyInput = document.getElementById('api-key');
    const modelSelect = document.getElementById('model-select');
    const saveBtn = document.getElementById('save-btn');
    const statusMsg = document.getElementById('status-msg');

    // Load settings
    fetch('/api/settings')
        .then(res => res.json())
        .then(data => {
            if (data.api_key) apiKeyInput.value = data.api_key;
            if (data.model) modelSelect.value = data.model;
        })
        .catch(err => console.error('Failed to load settings:', err));

    // Save settings
    saveBtn.addEventListener('click', () => {
        const apiKey = apiKeyInput.value.trim();
        const model = modelSelect.value;

        fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                api_key: apiKey,
                model: model
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                statusMsg.textContent = '设置已保存！';
                setTimeout(() => statusMsg.textContent = '', 3000);
            }
        })
        .catch(err => {
            statusMsg.textContent = '保存失败: ' + err.message;
            statusMsg.style.color = 'red';
        });
    });
});
