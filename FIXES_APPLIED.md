# Fixes Applied to CPS Energy Tools

## Issue: 405 Method Not Allowed for API Endpoints (2025-05-29)

### Problem
- Website loads successfully but POST requests to `/api/pole-comparison` return 405 Method Not Allowed
- API routes were not being registered properly on Heroku deployment

### Root Causes Identified
1. **Import Path Issue**: The import path `backend.cps_tools.api` was failing because of module resolution differences between local and Heroku environments
2. **Route Registration Order**: API routes were being registered AFTER static file mounts, causing them to be shadowed by the catch-all route

### Fixes Applied

1. **Fixed Import Path** (backend/main.py):
   - Changed from: `from backend.cps_tools.api import routers`
   - Changed to: `from .cps_tools.api import routers` (relative import)
   - This ensures proper module resolution when running as `backend.main:app`

2. **Reordered Route Registration** (backend/main.py):
   - Moved API router inclusion to happen BEFORE static file mounting
   - This prevents the catch-all route from intercepting API requests
   - Added comments to clarify the importance of registration order

3. **Enhanced Error Handling** (backend/main.py):
   - Added detailed error messages for import failures
   - Added a generic Exception handler to catch any import errors
   - This provides better debugging information in logs

### Testing
- Created `test_heroku_deployment.py` to verify:
  - Health endpoint is accessible and shows registered routes
  - POST method is allowed on `/api/pole-comparison` endpoint

### Deployment Steps
1. Commit the changes to backend/main.py
2. Push to Heroku: `git push heroku main`
3. Monitor logs: `heroku logs --tail`
4. Run test script: `python test_heroku_deployment.py`

### Verification
After deployment, the following should work:
- Health check at `/health` should list all API routes
- POST requests to `/api/pole-comparison` should not return 405
- All other API endpoints should be accessible

## Issue: 404 Not Found on Page Refresh (2025-05-29)

### Problem
- When users refresh the page on any route (e.g., `/pole-comparison`), the server returns `{"detail":"Not Found"}`
- This is a classic Single Page Application (SPA) routing issue

### Root Cause
- The root static mount (`app.mount("/", StaticFiles(...))`) was intercepting all requests before they could reach the catch-all route
- When refreshing on `/pole-comparison`, the static file handler looked for a file at that path, didn't find it, and returned 404

### Fix Applied (backend/main.py)

1. **Removed Root Static Mount**:
   - Removed the problematic `app.mount("/", StaticFiles(...))` that was intercepting all requests
   - Kept only the `/assets` mount for serving static assets

2. **Updated Catch-All Route**:
   - Modified the `catch_all` function to properly handle SPA routing
   - The new logic:
     - First checks if the requested path is an actual static file (like `cps-tools-logo.svg`)
     - If it's a file, serves the file directly
     - If it's not a file, serves `index.html` to let React Router handle client-side routing

### Result
- Refreshing on any route (e.g., `/pole-comparison`) now correctly serves `index.html`
- React Router takes over and displays the appropriate component
- Static files like logos and favicons continue to work correctly
- API endpoints remain unaffected

### Testing
After deployment, verify:
1. Navigate to `/pole-comparison` and refresh the page - should load correctly
2. Direct navigation to any route should work
3. Static files like `/cps-tools-logo.svg` should still load
4. API endpoints should continue functioning normally
