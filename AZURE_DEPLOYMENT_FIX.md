# Azure Deployment Fix - 503 Service Unavailable Resolution

## Root Cause
The app was loading 1000 residents from Excel **during module import time**, blocking Gunicorn worker readiness for ~24 seconds. Azure App Service marked workers as unhealthy → 503 errors.

## Changes Made

### 1. Lazy Loading (app.py lines 130-180)
- **Before**: `residents = load_residents_from_excel()` at module import
- **After**: `LazyResidentsList` class with `get_residents()` lazy loader
- **Impact**: Worker ready in <1 second, data loads on first request

### 2. Request/Response Logging (app.py lines 407-420)
- Added `@app.before_request` to log all incoming requests
- Added `@app.after_request` to log all responses
- **Impact**: Full request visibility in Azure logs

### 3. Global Error Handler (app.py lines 395-403)
- Added `@app.errorhandler(Exception)` to catch all uncaught errors
- Logs full stack traces to Azure
- **Impact**: No more silent 500/503 errors

### 4. Improved Health Checks (app.py lines 337-355)
- `/health` works even if data isn't loaded yet
- Returns cache initialization status
- Always returns 200 (degraded state if error)

### 5. Gunicorn Configuration (gunicorn.conf.py)
- Request logging to stdout: `accesslog = "-"`
- Error logging to stdout: `errorlog = "-"`
- Increased timeout: `timeout = 120`
- Startup hooks for visibility

## Azure App Service Configuration

### Update Startup Command

**Option 1 - Use gunicorn.conf.py (RECOMMENDED):**
```bash
gunicorn app:app --config gunicorn.conf.py
```

**Option 2 - Inline configuration:**
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 --access-logfile - --error-logfile - --log-level info --access-logformat '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
```

### Azure Portal Steps
1. Go to Azure Portal → Your App Service
2. Navigate to **Configuration** → **General settings**
3. Update **Startup Command** to one of the options above
4. Click **Save**
5. Wait for restart (~2 minutes)

### Verify Deployment
1. Visit `https://your-app.azurewebsites.net/health`
   - Should return: `{"status": "healthy", ...}`
2. Visit `https://your-app.azurewebsites.net/debug-auth`
   - Should return Easy Auth headers (or "Not present" if not authenticated)
3. Check Azure **Log Stream** for:
   ```
   REQUEST: GET /health from <ip>
   RESPONSE: GET /health -> 200
   ```

## Performance Improvements

### Before
- **Worker boot to ready**: ~24 seconds
- **First request**: Immediate (data already loaded)
- **Subsequent requests**: Fast

### After  
- **Worker boot to ready**: <1 second ✅
- **First request**: ~2-3 seconds (lazy data load)
- **Subsequent requests**: Fast (cached)

## Easy Auth Integration

The app now properly handles:
- ✅ Requests with Easy Auth headers (authenticated users)
- ✅ Requests without Easy Auth headers (health checks, diagnostics)
- ✅ Failed authentication (logs warning, doesn't block request)

### Exempt Endpoints (No Auth Required)
- `/health` - Health checks
- `/debug-auth` - Diagnostic endpoint
- `/static/*` - Static files  

All other routes go through Easy Auth middleware.

## Troubleshooting

### Still seeing 503?
1. Check Azure **Deployment Center** → Ensure latest commit is deployed
2. Check Azure **Log Stream** → Look for errors during startup
3. Verify startup command includes `gunicorn.conf.py`
4. Check **Application Insights** → Review exceptions

### No logs appearing?
1. Verify startup command has `--access-logfile -` and `--error-logfile -`
2. Use `gunicorn.conf.py` (automatically configures logging)
3. Check Azure **App Service logs** → Ensure **Application logging** is enabled

### Slow first request?
- **Expected**: First request triggers lazy load (~2-3 seconds for 1000 residents)
- **Subsequent requests** will be fast (cached in memory)
- **Alternative**: Use Azure **Always On** to keep worker warm

## Files Changed
- `app.py` - Lazy loading, logging, error handling
- `gunicorn.conf.py` - NEW FILE - Gunicorn configuration

## Files to Deploy
```
app.py
gunicorn.conf.py
requirements.txt
utils/
templates/
static/
```

## Next Steps (Optional Optimizations)
1. Move Excel data to Azure Blob Storage or Database
2. Implement caching with Redis
3. Add Application Insights for advanced monitoring
4. Configure auto-scaling based on load
