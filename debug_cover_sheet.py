#!/usr/bin/env python3
"""
Debug script for cover sheet tool
"""

import json
import sys
from cover_sheet_tool import extract_cover_sheet_data, debug_design_labels

def main():
    if len(sys.argv) != 2:
        print("Usage: python debug_cover_sheet.py <spida_file.json>")
        return
    
    spida_file = sys.argv[1]
    
    try:
        with open(spida_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        print("=== DEBUGGING COVER SHEET EXTRACTION ===\n")
        
        # Show design labels
        debug_design_labels(json_data)
        
        # Extract cover sheet data with debug output
        cover_sheet_data = extract_cover_sheet_data(json_data)
        
        print("\n=== FINAL RESULTS ===")
        print(f"Total poles found: {len(cover_sheet_data['Poles'])}")
        
        for pole in cover_sheet_data['Poles']:
            print(f"Pole {pole['Station ID']}: Existing={pole['Existing Loading %']}, Final={pole['Final Loading %']}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 