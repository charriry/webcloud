# webcloud

A web-based AI chat application using Flask and Alibaba Qwen API.

## Features

- **Per-User Session Isolation**: Each user has their own isolated session with independent API key and model settings
- Multiple Qwen model support (Qwen-Turbo, Qwen-Plus, Qwen-Max, wanx-v1)
- Client-side conversation storage
- Clean and responsive UI

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Development Mode

```bash
python app.py
```

The application will run on `http://0.0.0.0:5000`

### Production Deployment

For production deployment with PM2:

```bash
pm2 start app.py --name webcloud --interpreter python3
```

## Configuration

### Session-Based Configuration (Per-User)

Each user can configure their own API key and model selection through the settings page (`/settings`). These settings are stored in encrypted session cookies and are isolated per user.

### Global Configuration (Optional)

You can also set global defaults using environment variables:

- `FLASK_SECRET_KEY`: Secret key for Flask session encryption (recommended for production)
- `ALI_QW_API_KEY`: Default Alibaba Qwen API key (used if user hasn't set their own)
- `ALI_QW_MODEL`: Default model selection (used if user hasn't set their own)

Example:
```bash
export FLASK_SECRET_KEY="your-secret-key-here"
export ALI_QW_API_KEY="sk-..."
export ALI_QW_MODEL="qwen-turbo"
python app.py
```

## Session Isolation

The application uses Flask sessions to ensure each user has isolated settings:

1. When User A sets their API key, it's stored in User A's session cookie
2. When User B accesses the application, they have a separate session and won't see User A's API key
3. Each user can have different API keys and model selections
4. Settings persist across page reloads for the same user (same browser session)

Configuration Priority (highest to lowest):
1. User session settings (per-user)
2. Environment variables (global)
3. Config file (global)
4. Default values
