# API Route Fixes

## Problem Identified

The application was experiencing `405 Method Not Allowed` errors on several key API endpoints:

```
POST /api/mrr-process - 405 Method Not Allowed
POST /api/spida-import - 405 Method Not Allowed  
POST /api/pole-comparison - 405 Method Not Allowed
```

## Root Causes

The investigation revealed two primary issues:

1. **Inconsistent Router Prefix Configuration:**
   - In `mrr_process.py` and `spida.py`, the router was correctly defined with `prefix="/api"` but then endpoints were defined with paths like `/mrr-process`
   - In `pole_compare.py`, the router was defined without a prefix (`router = APIRouter()`) but then the endpoint was defined with the full path `/api/pole-comparison` 
   - This inconsistency led to route registration conflicts

2. **Double Registration of Routers:**
   - In `backend/main.py`, the MRR router was being registered twice:
     - Once through the combined router: `app.include_router(_tool_routers)`
     - And again directly: `app.include_router(mrr_process.router)`
   - This double registration caused routing conflicts where FastAPI couldn't properly match request paths

## Fixes Applied

1. **Standardized Router Configurations:**
   - Updated `pole_compare.py` to use `router = APIRouter(prefix="/api")` like the other routers
   - Fixed route path in `pole_compare.py` to use just `/pole-comparison` instead of `/api/pole-comparison`
   - This ensures consistent route registration patterns across all routers

2. **Eliminated Double Registration:**
   - Removed the direct inclusion of the MRR router from `backend/main.py`
   - Kept only the combined router inclusion via `app.include_router(_tool_routers)`
   - This ensures each router is registered exactly once

3. **Added Diagnostic Endpoints:**
   - Added debug endpoints to each router to help with testing and troubleshooting:
     - `/api/mrr-debug` and `/api/mrr-routes` 
     - `/api/spida-debug` and `/api/spida-routes`
     - `/api/pole-compare-debug` and `/api/pole-compare-routes`
   - Added a global route listing endpoint to the main app: `/debug-all-routes`

4. **Created Testing Script:**
   - Developed `test_fixed_endpoints.py` to verify the fixes are working
   - The script tests various endpoints to ensure they respond with the correct status codes
   - Specifically checks that previously problematic endpoints no longer return 405 errors

## How to Test

To verify the fixes have been properly applied, run:

```bash
python test_fixed_endpoints.py
```

This will check:
1. Health endpoint functionality
2. Route debugging endpoints
3. The problematic API endpoints to ensure they now accept POST requests correctly

The script should report all tests passing if the fixes have been successfully applied.

## Note for Deployment

After applying these fixes, you'll need to:

1. Deploy the updated code to your server (Heroku in this case)
2. Run the test script against your deployed instance to confirm all routes are working correctly
3. Monitor your logs to ensure no more 405 errors appear

The changes made were targeted and minimal, focusing only on the routing configuration without modifying any business logic, so the risk of regressions should be low.
