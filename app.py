# ...existing code...
from flask import Flask, render_template, request, jsonify
import dashscope
import json
import os
import uuid
from datetime import datetime

app = Flask(__name__)

CONFIG_FILE = 'config.json'
CONVERSATIONS_FILE = 'conversations.json'

def load_config():
    # Load model from config file, but always prefer environment variables for secrets/config
    cfg = {"api_key": "", "model": "qwen-turbo"}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                file_cfg = json.load(f)
                cfg.update(file_cfg)
        except Exception:
            pass

    # API key MUST come from environment variable if present
    cfg['api_key'] = os.environ.get('ALI_QW_API_KEY', cfg.get('api_key', ''))
    # Allow overriding model via environment too
    cfg['model'] = os.environ.get('ALI_QW_MODEL', cfg.get('model', 'qwen-turbo'))
    return cfg

def save_config(config):
    # Only persist non-secret settings (like model) to disk.
    # We avoid saving API keys to disk here.
    safe_cfg = {k: v for k, v in config.items() if k != 'api_key'}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(safe_cfg, f, ensure_ascii=False, indent=2)

def load_conversations_data():
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_conversations_data(data):
    with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
        api_key = data.get('api_key')
        model = data.get('model')

        # Set API key into environment for current process only
        if api_key:
            os.environ['ALI_QW_API_KEY'] = api_key

        # Persist model selection to config.json
        config = load_config()
        if model:
            config['model'] = model
        save_config(config)

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
    }
    try:
        sdk_key = getattr(dashscope, 'api_key', None)
        flags["dashscope_api_key_set"] = bool(sdk_key)
    except Exception:
        flags["dashscope_api_key_set"] = False
    return jsonify(flags)

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    data = load_conversations_data()
    conv_list = []
    for cid, cdata in data.items():
        conv_list.append({
            'id': cid,
            'title': cdata.get('title', 'New Chat'),
            'updated_at': cdata.get('updated_at', '')
        })
    # Sort by updated_at descending
    conv_list.sort(key=lambda x: x['updated_at'], reverse=True)
    return jsonify(conv_list)

@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    data = load_conversations_data()
    if conversation_id in data:
        return jsonify(data[conversation_id])
    return jsonify({"error": "Conversation not found"}), 404

@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    data = load_conversations_data()
    if conversation_id in data:
        del data[conversation_id]
        save_conversations_data(data)
        return jsonify({"status": "success"})
    return jsonify({"error": "Conversation not found"}), 404

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    conversation_id = data.get('conversation_id')
    
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
    
    # Load conversations
    conversations_data = load_conversations_data()
    
    if conversation_id and conversation_id in conversations_data:
        current_conv = conversations_data[conversation_id]
    else:
        # Create new conversation
        conversation_id = str(uuid.uuid4())
        title = user_message[:30] + "..." if len(user_message) > 30 else user_message
        current_conv = {
            "id": conversation_id,
            "title": title,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": []
        }
        conversations_data[conversation_id] = current_conv

    # Prepare messages for API
    messages = []
    for msg in current_conv['messages']:
        messages.append({'role': msg['role'], 'content': msg['content']})
    messages.append({'role': 'user', 'content': user_message})

    try:
        response = dashscope.Generation.call(
            model=model,
            messages=messages,
            result_format='message',
        )
        
        if response.status_code == 200:
            assistant_content = response.output.choices[0].message.content
            
            # Update conversation data
            current_conv['messages'].append({'role': 'user', 'content': user_message})
            current_conv['messages'].append({'role': 'assistant', 'content': assistant_content})
            current_conv['updated_at'] = datetime.now().isoformat()
            
            save_conversations_data(conversations_data)
            
            return jsonify({
                "response": assistant_content,
                "role": "assistant",
                "conversation_id": conversation_id,
                "title": current_conv['title']
            })
        else:
            return jsonify({"error": f"API Error: {response.code} - {response.message}"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, port=5000)
# ...existing code...