# Settings Configuration Guide

## Overview
The Settings page has been redesigned to focus on user account management, appearance preferences, and social network connections. All API keys are now configured via environment variables (`.env`) rather than in the UI.

## Features

### 1. Account Settings
- **User ID**: Unique identifier (copyable)
- **Email**: Your login email address (read-only)
- **Display Name**: Editable name visible in the app

The account settings are persisted to localStorage and integrated with Supabase authentication.

### 2. Appearance (Theme)
Three theme options:
- **Light**: Bright interface for daytime use
- **Dark**: Dark interface for reduced eye strain
- **System**: Automatically matches your OS preference

Theme preference is saved to localStorage under `openshorts-theme`.

### 3. Connected Networks
Connect your social media accounts to enable direct sharing of generated clips:
- LinkedIn
- TikTok
- YouTube
- Facebook
- Instagram

Network connections are stored locally in localStorage under `openshorts-connected-networks`.

## API Keys Configuration

### No UI Input for API Keys
API keys are NO LONGER configurable in the Settings UI. This was changed for security reasons:
- Prevents accidental exposure
- Keeps sensitive data server-side only
- Simplifies the UI

### Environment Variables (Backend)
All API keys must be configured in the `.env` file (backend/root):

```env
# Gemini API
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-3.5-flash

# OpenAI API (fallback)
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4.1-mini

# ElevenLabs API (for video dubbing)
ELEVENLABS_API_KEY=your_elevenlabs_key_here

# Upload-Post API (social media publishing)
UPLOAD_POST_API_KEY=your_uploadpost_key_here
```

### Accessing API Keys in Frontend
If frontend components need to verify API availability:

```javascript
import { useAuth } from '@/state/AuthContext';

// Check if backend has required APIs configured
// (The backend exposes an endpoint to check configured services)
```

### Backend Endpoint: Check Available Services
```
GET /api/available-services
```

Response example:
```json
{
  "gemini": true,
  "openai": true,
  "elevenlabs": true,
  "uploadpost": true
}
```

## Implementation Details

### Files Modified
- `dashboard/src/pages/Settings.jsx` - Complete redesign with 4 sections
- `dashboard/src/state/ThemeContext.jsx` - New theme management context
- `dashboard/src/main.jsx` - ThemeProvider integration
- `dashboard/tailwind.config.js` - Dark mode class support
- `dashboard/src/index.css` - Theme-aware CSS variables

### Storage Keys
| Key | Purpose |
|-----|---------|
| `openshorts-theme` | User's theme preference (dark/light/system) |
| `openshorts-display-name` | User's display name (cached locally) |
| `openshorts-connected-networks` | JSON object of connected social networks |

### Theme Implementation
- Uses Tailwind's `class` darkMode strategy
- CSS variables for dynamic color switching
- Respects system preference when "System" is selected
- Smooth transitions between themes

## Future Enhancements
1. OAuth integration for social networks (currently UI-only)
2. Direct profile updates to Supabase user metadata
3. API key validation endpoint in backend
4. Service status indicators on Settings page
5. Advanced account security settings (2FA, session management)

## Security Notes
- 🔒 API keys are environment variables only (never in browser)
- 🔒 User credentials are managed by Supabase Auth
- 🔒 Social network settings are stored locally only
- 🔒 Theme preferences are user-specific and non-sensitive

