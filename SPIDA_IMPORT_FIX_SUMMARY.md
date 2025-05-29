# SpidaCalc Import Tool - Insulator Extraction Fix Summary

## Problem
The SpidaCalc import tool was not extracting insulators/attachments from Katapult JSON files. The React table was showing empty rows with no insulator data.

## Root Cause
The attachment extraction logic was looking in the wrong locations within the Katapult JSON structure:
1. Looking for attachments in connection endpoints (`end1_height`, `end2_height`)
2. Looking for PhotoFirst data in the wrong location
3. Not accessing the `photos` section of the JSON where the actual attachment data is stored

## Solution Implemented

### 1. Updated `extract_attachments` function in `cps_tools/core/katapult/converter.py`
- Now accepts the full Katapult JSON instead of just nodes and connections
- Properly navigates to `photos` → `photofirst_data` → `wire/equipment/guying` categories
- Extracts attachment height, phase information from trace data, and determines crossarm placement
- Uses node_id as the SCID for consistency with the SPIDA conversion

### 2. Updated API endpoint in `backend/cps_tools/api/spida.py`
- Changed to pass the full `kata_json` to `extract_attachments` instead of just nodes/connections
- This allows access to the photos and traces sections needed for attachment extraction

### 3. Added SCID normalization in `cps_tools/core/katapult/utils.py`
- Created `normalize_scid` function to ensure consistent SCID formatting across the pipeline
- Handles various SCID formats (string, int, nested dict with 'value' key)

### 4. Enhanced debugging
- Added comprehensive logging throughout the extraction process
- Logs show:
  - Number of attachments found per node
  - SCID mappings
  - Attachment extraction from photofirst_data
  - Final insulator counts after seeding

## Key Technical Details

### Katapult JSON Structure
Attachments are stored in:
```
kata_json
  └── nodes
      └── [node_id]
          └── photos
              └── [photo_id] (where association == "main")
  └── photos
      └── [photo_id]
          └── photofirst_data
              ├── wire
              ├── equipment
              └── guying
                  └── [item_id]
                      ├── _measured_height (in feet)
                      ├── _trace (reference to trace_data)
                      └── cable_type/equipment_type
```

### Phase Determination Logic
- Checks trace data for cable_type/equipment_type
- Infers phase from keywords: "primary", "neutral", "secondary", "service", "street light"
- Determines crossarm placement based on phase type

### Unit Conversions
- Attachment heights remain in feet during extraction
- Conversion to meters happens during insulator seeding
- Distance from top = pole height (m) - attachment height (ft) × 0.3048

## Testing Recommendations
1. Upload a Katapult JSON file with known attachment data
2. Check console logs for extraction results
3. Verify insulators appear in the React table
4. Confirm attachment heights and phases are correct
5. Test the download functionality for the converted SPIDA file

## Future Improvements
1. Make client file name and engineer name configurable (currently hardcoded)
2. Add support for additional attachment metadata
3. Improve error handling for missing photo data
4. Add unit tests for the extraction logic
