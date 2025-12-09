# ...existing code...
from flask import Flask, render_template, request, jsonify, session
import dashscope
import json
import os
import uuid
from datetime import datetime

app = Flask(__name__)

# Configure secret key for session encryption
# Generate a random secret key if not provided via environment variable
# WARNING: Without FLASK_SECRET_KEY set, sessions will be invalidated on app restart
if not os.environ.get('FLASK_SECRET_KEY'):
    print("WARNING: FLASK_SECRET_KEY not set. Using random key. Sessions will be lost on restart.")
    print("Set FLASK_SECRET_KEY environment variable for persistent sessions in production.")
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())

CONFIG_FILE = 'config.json'
CONVERSATIONS_FILE = 'conversations.json'

def load_config():
    """
    Load configuration with the following priority (highest to lowest):
    1. User session (per-user settings)
    2. Environment variables (global settings)
    3. Config file (global settings)
    4. Default values
    """
    cfg = {"api_key": "", "model": "qwen-turbo"}
    
    # Load from config file (lowest priority)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                file_cfg = json.load(f)
                cfg.update(file_cfg)
        except Exception:
            pass

    # Check environment variables (medium priority)
    env_api_key = os.environ.get('ALI_QW_API_KEY')
    env_model = os.environ.get('ALI_QW_MODEL')
    if env_api_key:
        cfg['api_key'] = env_api_key
    if env_model:
        cfg['model'] = env_model
    
    # Check user session (highest priority - per-user override)
    session_api_key = session.get('api_key')
    session_model = session.get('model')
    if session_api_key:
        cfg['api_key'] = session_api_key
    if session_model:
        cfg['model'] = session_model
    
    return cfg

def save_config(config):
    """
    Save configuration to user session (per-user settings).
    We no longer save to disk to avoid sharing settings across users.
    Note: This function is kept for backward compatibility but is no longer used internally.
    """
    if 'api_key' in config:
        if config['api_key']:
            session['api_key'] = config['api_key']
        else:
            session.pop('api_key', None)
    if 'model' in config:
        if config['model']:
            session['model'] = config['model']

def load_conversations_data():
    # Server-side persistence is deprecated; keep for backward compatibility only.
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_conversations_data(_data):
    # No-op to avoid storing any user content on the server.
    # This intentionally disables server-side conversation persistence.
    return

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'POST':
        data = request.json or {}
        
        # Store API key and model in user session (per-user settings)
        # Support partial updates: only update fields that are provided
        
        # Handle API key: accept empty string to clear, or non-empty to set
        if 'api_key' in data:
            api_key = data['api_key']
            if api_key:
                session['api_key'] = api_key
            else:
                # Clear API key from session if empty string is provided
                session.pop('api_key', None)
        
        # Handle model: always update if provided
        if 'model' in data and data['model']:
            session['model'] = data['model']

        return jsonify({"status": "success"})

    # GET: return whether API key exists (do NOT return raw key), and the model
    cfg = load_config()
    return jsonify({
        "api_key_set": bool(cfg.get('api_key')),
        "model": cfg.get('model', 'qwen-turbo')
    })

# 新增调试接口：返回相关环境变量与 SDK 内部 key 是否存在（仅布尔，不返回密钥）
@app.route('/api/debug-env', methods=['GET'])
def debug_env():
    flags = {
        "ALI_QW_API_KEY_in_os_environ": bool(os.environ.get('ALI_QW_API_KEY')),
        "ALI_QW_MODEL_in_os_environ": bool(os.environ.get('ALI_QW_MODEL')),
        "api_key_in_session": bool(session.get('api_key')),
        "model_in_session": bool(session.get('model')),
    }
    try:
        sdk_key = getattr(dashscope, 'api_key', None)
        flags["dashscope_api_key_set"] = bool(sdk_key)
    except Exception:
        flags["dashscope_api_key_set"] = False
    return jsonify(flags)

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    # Deprecated on server: conversations are stored client-side now.
    return jsonify([])

@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    # Deprecated on server: conversations are stored client-side now.
    return jsonify({"error": "Conversation storage is client-side now"}), 410

@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    # Deprecated on server: conversations are stored client-side now.
    return jsonify({"error": "Conversation storage is client-side now"}), 410

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    user_message = data.get('message')
    client_messages = data.get('messages')  # preferred: full history including the new user msg
    conversation_id = data.get('conversation_id')  # echoed back if provided

    config = load_config()
    api_key = config.get('api_key')
    model = config.get('model', 'qwen-turbo')

    # If API key not present in saved settings, try environment variable, then SDK cache
    if not api_key:
        env_key = os.environ.get('ALI_QW_API_KEY')
        sdk_key = None
        try:
            sdk_key = getattr(dashscope, 'api_key', None)
        except Exception:
            sdk_key = None

        if env_key:
            api_key = env_key
        elif sdk_key:
            api_key = sdk_key
        else:
            return jsonify({"error": "请先在设置页面或环境变量中配置 API Key"}), 400

    dashscope.api_key = api_key

    # Build message list: prefer client-provided full history
    messages = []
    if isinstance(client_messages, list) and all(isinstance(m, dict) for m in client_messages):
        # Basic shape validation
        for m in client_messages:
            role = m.get('role')
            content = m.get('content')
            if not isinstance(role, str) or not isinstance(content, str):
                return jsonify({"error": "messages 中的每条消息必须包含字符串类型的 role 与 content"}), 400
        messages = client_messages
    elif isinstance(user_message, str) and user_message.strip():
        messages = [{'role': 'user', 'content': user_message.strip()}]
    else:
        return jsonify({"error": "缺少消息内容。请提供 messages（推荐）或 message"}), 400

    try:
        response = dashscope.Generation.call(
            model=model,
            messages=messages,
            result_format='message',
        )

        if response.status_code == 200:
            assistant_content = response.output.choices[0].message.content
            return jsonify({
                "response": assistant_content,
                "role": "assistant",
                "conversation_id": conversation_id
            })
        else:
            return jsonify({"error": f"API Error: {response.code} - {response.message}"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=False, port=5000)
# ...existing code...