# API Keys Configuration Guide

## Overview
All API keys in OpenShorts are configured via environment variables in the `.env` file located at the project root. This approach ensures that sensitive credentials are never exposed in the UI and follow industry security best practices.

## Configuration Steps

### 1. Open or Create `.env` File
- **Location**: `/Volumes/SSD_DEV/projects/web/saasvideo/.env`
- If the file doesn't exist, create it at the project root

### 2. Add API Keys

#### Google Gemini (REQUIRED for AI analysis)
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash
GEMINI_TIMEOUT_SECONDS=60
GEMINI_TRANSLATE_MODEL=gemini-3.5-flash
GEMINI_INPUT_PRICE_PER_MILLION=0.075
GEMINI_OUTPUT_PRICE_PER_MILLION=0.30
```

**How to get:**
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikeys)
2. Create a new API key
3. Copy and paste it to `GEMINI_API_KEY`

#### OpenAI (OPTIONAL - fallback AI provider)
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT_SECONDS=60
OPENAI_TRANSLATE_MODEL=gpt-4.1-mini
OPENAI_INPUT_PRICE_PER_1K=0.00015
OPENAI_OUTPUT_PRICE_PER_1K=0.00060
```

**How to get:**
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy and paste it to `OPENAI_API_KEY`

#### ElevenLabs (OPTIONAL - for video dubbing/translation)
```env
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
```

**How to get:**
1. Go to [ElevenLabs Dashboard](https://elevenlabs.io/app/settings/api-keys)
2. Create a new API key
3. Copy and paste it to `ELEVENLABS_API_KEY`

#### Upload-Post (OPTIONAL - for social media publishing)
```env
UPLOAD_POST_API_KEY=your_uploadpost_api_key_here
```

**How to get:**
1. Go to [Upload-Post Dashboard](https://app.upload-post.com/api-keys)
2. Create a new API key
3. Copy and paste it to `UPLOAD_POST_API_KEY`

### 3. AWS S3 (OPTIONAL - for video backup)
```env
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your_bucket_name
AWS_S3_PUBLIC_BUCKET=your_public_bucket_name
```

**How to get:**
1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam)
2. Create an IAM user with S3 access
3. Generate access keys
4. Create S3 buckets

### 4. Supabase (REQUIRED for authentication & database)
```env
SUPABASE_URL=https://your-supabase-url.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_key
```

**How to get:**
1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Go to Settings > API
3. Copy the URL
4. Copy the service role key (or create a new one)

### 5. Optional Configurations
```env
# Assembly AI for transcription
ASSEMBLYAI_API_KEY=your_assemblyai_key
ASSEMBLYAI_DEFAULT_LANGUAGE=fr
ASSEMBLYAI_TIMEOUT_SECONDS=600
ASSEMBLYAI_POLL_INTERVAL_SECONDS=3

# Job processing
MAX_CONCURRENT_JOBS=5

# YouTube support
YOUTUBE_COOKIES=/app/cookies.txt
DISABLE_YOUTUBE_URL=false

# AI Provider selection
AI_PROVIDER=hybrid  # Options: gemini, openai, hybrid

# Transcriber provider
TRANSCRIBER_PROVIDER=assemblyai  # Fallback: faster_whisper
TRANSCRIBER_FALLBACK=faster_whisper
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

## Complete `.env` Example

```dotenv
# ─── AWS S3 Configuration ───────────────────────────────────────────
AWS_ACCESS_KEY_ID=AKIA2NTNHA3YXXXXXX
AWS_SECRET_ACCESS_KEY=i+uaPcIX7/WiICEmHnq6fRTWr9dq8a4mtXXXXXX
AWS_REGION=us-east-1
AWS_S3_BUCKET=wouri-bucket
AWS_S3_PUBLIC_BUCKET=wouri-bucket
MAX_CONCURRENT_JOBS=5

# ─── YouTube Cookies ────────────────────────────────────────────────
YOUTUBE_COOKIES=/app/cookies.txt

# ─── Transcription (Assembly AI + Fallback) ─────────────────────────
ASSEMBLYAI_API_KEY=4dc428c4d61f4810baeefc584c6825eb
ASSEMBLYAI_DEFAULT_LANGUAGE=fr
ASSEMBLYAI_TIMEOUT_SECONDS=600
ASSEMBLYAI_POLL_INTERVAL_SECONDS=3
TRANSCRIBER_PROVIDER=assemblyai
TRANSCRIBER_FALLBACK=faster_whisper
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# ─── AI Model Provider ──────────────────────────────────────────────
AI_PROVIDER=hybrid

# ─── Google Gemini (Primary AI) ────────────────────────────────────
GEMINI_API_KEY=AQ.Ab8RN6IvreiebbhYAuaDh477kdNPxxxxx
GEMINI_MODEL=gemini-3.5-flash
GEMINI_TIMEOUT_SECONDS=60
GEMINI_TRANSLATE_MODEL=gemini-3.5-flash
GEMINI_INPUT_PRICE_PER_MILLION=0.075
GEMINI_OUTPUT_PRICE_PER_MILLION=0.30

# ─── OpenAI (Fallback AI) ──────────────────────────────────────────
OPENAI_API_KEY=sk-proj-scAw0ByPXwyU-UeyBYgFqtnpDGXKhATExxxxx
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT_SECONDS=60
OPENAI_TRANSLATE_MODEL=gpt-4.1-mini
OPENAI_INPUT_PRICE_PER_1K=0.00015
OPENAI_OUTPUT_PRICE_PER_1K=0.00060

# ─── Assembly AI Pricing ────────────────────────────────────────────
ASSEMBLYAI_PRICE_PER_HOUR_USD=0.37

# ─── Supabase ───────────────────────────────────────────────────────
SUPABASE_URL=https://csprtidrigghqizhqslp.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...xxxxx

# ─── Optional: ElevenLabs (Video Dubbing) ─────────────────────────
# ELEVENLABS_API_KEY=sk_xxxxx

# ─── Optional: Upload-Post (Social Media Publishing) ────────────
# UPLOAD_POST_API_KEY=ey_xxxxx
```

## Verifying Configuration

### 1. Check Status in UI
- Go to Settings page
- Look at "Service Status" section
- Each service will show "Ready" or "Not configured"

### 2. Check Backend
- The endpoint `/api/services/status` shows which services are available
- Example response:
```json
{
  "gemini": {"available": true, "name": "Google Gemini"},
  "openai": {"available": true, "name": "OpenAI"},
  "elevenlabs": {"available": false, "name": "ElevenLabs"},
  "uploadpost": {"available": false, "name": "Upload-Post"},
  "aws_s3": {"available": true, "name": "AWS S3"},
  "supabase": {"available": true, "name": "Supabase"}
}
```

### 3. Test Processing
- Try processing a video
- If errors occur, check the API key configuration

## Security Best Practices

✅ **DO:**
- Store sensitive keys in `.env` file
- Never commit `.env` to version control
- Regenerate keys if they're compromised
- Use separate keys for development and production
- Rotate keys regularly
- Use service accounts with minimal permissions

❌ **DON'T:**
- Share API keys in messages or emails
- Store keys in the browser
- Hardcode keys in the codebase
- Use production keys in development
- Commit `.env` to Git
- Expose keys in screenshots

## Troubleshooting

### "Missing API Key" Error
- Check that the key is set in `.env`
- Ensure Docker/server has restarted after changing `.env`
- Verify the key is valid and not expired

### Service Shows "Not configured"
- Check the key exists in `.env`
- Verify spelling matches exactly
- Restart the backend server

### 401/403 Errors During Processing
- The API key is likely invalid or expired
- Generate a new key from the service provider
- Update `.env` and restart

## Support Links

- [Google Gemini API Keys](https://aistudio.google.com/app/apikeys)
- [OpenAI API Keys](https://platform.openai.com/api-keys)
- [ElevenLabs API Keys](https://elevenlabs.io/app/settings/api-keys)
- [Upload-Post API Keys](https://app.upload-post.com/api-keys)
- [AWS IAM Console](https://console.aws.amazon.com/iam)
- [Supabase Dashboard](https://supabase.com/dashboard)

