# Assistant Live Demo - Deployment Guide

This guide provides step-by-step instructions for deploying the Assistant Live Demo to various cloud platforms for alpha testing.

## 🚀 Quick Deployment Options

### 1. Vercel (Recommended for Frontend Integration)

**Prerequisites:**
- GitHub account
- Vercel account (free tier available)

**Step-by-Step:**

1. **Prepare Repository:**
   ```bash
   # Ensure all files are committed
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Deploy to Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Vercel auto-detects `vercel.json` configuration
   - Click "Deploy"

3. **Configure Environment (Optional):**
   ```
   CORS_ORIGINS=https://your-frontend-domain.com
   DATABASE_PATH=/tmp/assistant_demo.db
   ```

4. **Test Deployment:**
   ```bash
   curl https://your-project.vercel.app/api/health
   ```

### 2. Streamlit Cloud (For Frontend)

**For Streamlit Frontend Deployment:**

1. **Prepare Repository:**
   - Ensure `streamlit/demo_streamlit.py` exists
   - Create `streamlit_requirements.txt` if needed

2. **Deploy:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect GitHub repository
   - Set main file path: `streamlit/demo_streamlit.py`
   - Configure secrets:
     ```
     API_BASE = "https://your-api.vercel.app"
     ```

3. **Test:**
   - Access your Streamlit app URL
   - Verify API connectivity

### 3. Railway (Alternative Platform)

**One-Click Deployment:**

1. **Install Railway CLI:**
   ```bash
   npm install -g @railway/cli
   ```

2. **Deploy:**
   ```bash
   cd assistant-live-demo
   railway login
   railway init
   railway add
   railway up
   ```

3. **Set Environment Variables:**
   ```bash
   railway variables set CORS_ORIGINS="*"
   railway variables set API_HOST="0.0.0.0"
   railway variables set API_PORT="8000"
   ```

### 4. Docker Deployment

**Local Docker:**

```bash
# Build image
cd assistant-live-demo
docker build -t assistant-demo .

# Run container
docker run -d \
  --name assistant-demo \
  -p 8000:8000 \
  -e CORS_ORIGINS="*" \
  assistant-demo

# Check health
curl http://localhost:8000/api/health
```

**Docker Compose (Full Stack):**

```bash
# Start both API and Streamlit
docker-compose up -d

# Check services
docker-compose ps
docker-compose logs
```

### 5. Heroku Deployment

**Prerequisites:**
- Heroku CLI installed
- Heroku account

**Steps:**

```bash
# Login to Heroku
heroku login

# Create app
heroku create your-assistant-demo

# Set environment variables
heroku config:set CORS_ORIGINS="*"
heroku config:set API_HOST="0.0.0.0"

# Deploy
git push heroku main

# Test
curl https://your-assistant-demo.herokuapp.com/api/health
```

## 🔧 Environment Configuration

### Required Environment Variables

| Variable | Description | Default | Production Example |
|----------|-------------|---------|-------------------|
| `API_HOST` | Server bind address | `127.0.0.1` | `0.0.0.0` |
| `API_PORT` | Server port | `8000` | `8000` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` | `https://app.com,https://admin.com` |
| `DATABASE_PATH` | SQLite database path | `./assistant_demo.db` | `/tmp/assistant_demo.db` |

### Security Variables (enable one or both)

| Variable | Description | Default |
|----------|-------------|---------|
| `API_REQUIRE_KEY` | Enforce `x-api-key` header | `false` |
| `API_KEY` | The expected API key value | — |
| `JWT_REQUIRE` | Enforce Bearer JWT | `false` |
| `JWT_SECRET` | HMAC secret for signing/verifying tokens | — |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |

Dev token issuance (optional):

```
uvicorn assistant_api.main:app --reload --port 8000
# Then POST /auth/token to receive a Bearer token (requires JWT_SECRET).
```

### Platform-Specific Notes

**Vercel:**
- Use `/tmp/` for database path (ephemeral storage)
- Functions timeout: 10s (Hobby), 60s (Pro)
- Automatic HTTPS

**Railway:**
- Persistent storage available
- PostgreSQL addon available if needed
- Custom domains supported

**Heroku:**
- Ephemeral filesystem (SQLite data resets on restart)
- Consider Heroku Postgres for persistence
- Dyno sleeping on free tier

**Docker:**
- Full control over environment
- Persistent volumes for database
- Can run on any cloud provider

## 📊 Post-Deployment Setup

### 1. Populate Sample Data

**Method 1: Direct Script (if accessible):**
```bash
# If you have shell access
export API_BASE="https://your-deployed-api.com"
python seed_data.py
```

**Method 2: API Calls:**
```bash
# Submit sample messages via API
curl -X POST "https://your-api.vercel.app/api/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "platform": "email",
    "conversation_id": "setup_conv",
    "message_id": "setup_msg_1",
    "message_text": "Welcome! This is a test message for the demo.",
    "timestamp": "2025-09-18T10:00:00Z"
  }'
```

### 2. Verify Deployment

**Health Check:**
```bash
curl https://your-deployed-api.com/api/health
```

**Statistics Check:**
```bash
curl https://your-deployed-api.com/api/stats
```

**End-to-End Test:**
```bash
# Set API base URL
export API_BASE="https://your-deployed-api.com"

# Run comprehensive tests
python test_e2e_flow.py
```

### 3. Frontend Integration

**Update Frontend Configuration:**
```javascript
// In your frontend code
const API_BASE = 'https://your-deployed-api.com';

// Or use environment variables
const API_BASE = process.env.REACT_APP_API_BASE || 'http://127.0.0.1:8000';
```

**Streamlit Configuration:**
```python
# In streamlit app
API_BASE = os.getenv("API_BASE", "https://your-deployed-api.com")
```

## 🔍 Monitoring and Troubleshooting

### Health Monitoring

**Simple Uptime Check:**
```bash
#!/bin/bash
# monitor.sh
while true; do
  if curl -f https://your-api.com/api/health > /dev/null 2>&1; then
    echo "$(date): API is healthy"
  else
    echo "$(date): API is DOWN!"
  fi
  sleep 60
done
```

### Common Issues and Solutions

**1. CORS Errors:**
```bash
# Solution: Set proper CORS origins
heroku config:set CORS_ORIGINS="https://your-frontend.com"
# Or for Vercel: Add environment variable in dashboard
```

**2. Database Connection Issues:**
```bash
# For serverless platforms, use /tmp
DATABASE_PATH="/tmp/assistant_demo.db"
```

**3. Port Binding Issues:**
```bash
# Ensure proper host binding
API_HOST="0.0.0.0"
```

**4. Memory/Timeout Issues:**
- Check platform limits
- Optimize database queries
- Use pagination for large datasets

### Accessing Logs

**Vercel:**
- Dashboard → Project → Functions → View logs

**Railway:**
- Dashboard → Project → Deployments → View logs

**Heroku:**
```bash
heroku logs --tail --app your-app-name
```

**Docker:**
```bash
docker logs assistant-demo --follow
```

## 🔐 Security Considerations

### Production Checklist

- [ ] Set specific CORS origins (not `*`)
- [ ] Use HTTPS only
- [ ] Add API key authentication if needed
- [ ] Monitor API usage and rate limiting
- [ ] Regular security updates
- [ ] Database backup strategy

### Optional API Key Setup

```python
# Add to api/main.py for production
API_KEY = os.getenv("API_KEY")

@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if API_KEY and request.url.path.startswith("/api/"):
        provided_key = request.headers.get("x-api-key")
        if provided_key != API_KEY:
            return JSONResponse(
                {"error": "Invalid API key"}, 
                status_code=401
            )
    return await call_next(request)
```

## 📈 Scaling Considerations

### Database Upgrades

**For Production Use:**
- Consider PostgreSQL for better concurrency
- Implement connection pooling
- Add database migrations

**Example PostgreSQL Setup:**
```bash
# Railway PostgreSQL addon
railway add postgresql

# Update environment
DATABASE_URL="postgresql://user:pass@host:port/db"
```

### Performance Optimization

- Enable database indices (already included)
- Implement caching for frequently accessed data
- Use CDN for static assets
- Monitor response times and optimize slow endpoints

---

## 🎯 Ready for Alpha Testing!

Once deployed, your Assistant Live Demo will be accessible to:
- **Yash** for frontend integration
- **Stakeholders** for alpha testing
- **Team members** for validation

**Next Steps:**
1. Choose deployment platform
2. Follow platform-specific instructions
3. Verify deployment with health checks
4. Update frontend configuration
5. Run end-to-end tests
6. Share with team for alpha testing

**Support:** Contact Sankalp for deployment assistance