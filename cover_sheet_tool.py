#!/usr/bin/env python3
"""
CPS Delivery Tool - Cover Sheet Tool
Python script to extract cover sheet information from a SPIDAcalc JSON file.

This script extracts project information and pole data for documentation purposes.
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import time
from math import radians, sin, cos, sqrt, atan2

def get_address_from_coords(latitude: float, longitude: float) -> str:
    """
    Get address from coordinates using OpenStreetMap's Nominatim service.
    Includes rate limiting and error handling.
    """
    try:
        # Rate limiting - Nominatim has a 1 second usage policy
        time.sleep(1)
        
        # Make the request to Nominatim
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
        headers = {
            'User-Agent': 'CPS-Energy-Tools/1.0'  # Required by Nominatim's usage policy
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract address components
        address = data.get('address', {})
        house_number = address.get('house_number', '')
        road = address.get('road', '')
        city = address.get('city', '') or address.get('town', '') or address.get('village', '')
        
        # Build address string
        full_address = " ".join(filter(None, [house_number, road]))
        if city:
            full_address += f", {city}"
            
        return full_address or "Address not found"
        
    except Exception as e:
        print(f"Warning: Could not get address from coordinates: {e}")
        return "Address lookup failed"

def format_date(date_str: str) -> str:
    """Format date as MM/DD/YYYY if possible."""
    try:
        date = datetime.fromisoformat(date_str)
        return date.strftime('%m/%d/%Y')
    except Exception:
        return date_str


def debug_design_labels(json_data: Dict[str, Any]) -> None:
    """Debug function to print all design labels found in the JSON data"""
    print("DEBUG: Design labels and analysis results found in the file:")
    leads = json_data.get('leads', [])
    if not isinstance(leads, list):
        leads = []
    
    for lead_idx, lead in enumerate(leads):
        if not isinstance(lead, dict):
            continue
        locations = lead.get('locations', [])
        if not isinstance(locations, list):
            continue
        
        for loc_idx, loc in enumerate(locations):
            if not isinstance(loc, dict):
                continue
            pole_id = loc.get('label', '')
            designs = loc.get('designs', [])
            
            print(f"  Pole {pole_id}:")
            for design_idx, design in enumerate(designs):
                if not isinstance(design, dict):
                    continue
                design_label = design.get('label', '')
                layer_type = design.get('layerType', '')
                
                # Check for analysis results
                analysis_list = design.get('analysis', [])
                stress_results = []
                
                if isinstance(analysis_list, list):
                    for design_case in analysis_list:
                        if isinstance(design_case, dict):
                            results = design_case.get('results', [])
                            if isinstance(results, list):
                                for result in results:
                                    if isinstance(result, dict):
                                        analysis_type = result.get('analysisType', '')
                                        unit = result.get('unit', '')
                                        actual = result.get('actual', 0)
                                        if analysis_type.upper() == 'STRESS' and unit.upper() == 'PERCENT':
                                            stress_results.append(f"{actual:.1f}%")
                
                if stress_results:
                    max_stress = max(float(s.replace('%', '')) for s in stress_results)
                    stress_info = f", stress values: [{', '.join(stress_results)}], max: {max_stress:.1f}%"
                else:
                    stress_info = ", no stress results"
                print(f"    Design {design_idx}: '{design_label}' (layerType: '{layer_type}'{stress_info})")
    print("END DEBUG\n")


def extract_cover_sheet_data(json_data: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure json_data is a dictionary
    if not isinstance(json_data, dict):
        json_data = {}
    
    # Project info
    job_number = json_data.get('label', '')
    date = format_date(json_data.get('date', ''))
    
    # Safe access to nested dictionaries
    client_data = json_data.get('clientData', {})
    if not isinstance(client_data, dict):
        client_data = {}
    location = client_data.get('generalLocation', '')
    
    address = json_data.get('address', {})
    if not isinstance(address, dict):
        address = {}
    city = address.get('city', '')
    
    engineer = json_data.get('engineer', '')

    # Poles
    poles = []
    total_plas = 0
    unique_pole_ids = set()
    project_address = ''  # Will store address from first pole's coordinates

    leads = json_data.get('leads', [])
    if not isinstance(leads, list):
        leads = []
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        locations = lead.get('locations', [])
        if not isinstance(locations, list):
            continue
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            pole_id = loc.get('label', '')
            unique_pole_ids.add(pole_id)
            existing_loading = None
            final_loading = None
            notes = ''
            print(f"  Processing pole: {pole_id}")

            # Extract coordinates from SPIDA's geographicCoordinate (lon, lat order)
            geo = loc.get('geographicCoordinate', {})
            coords = geo.get('coordinates', [])  # Expected format: [longitude, latitude]
            if isinstance(coords, list) and len(coords) == 2:
                longitude, latitude = coords  # Unpack in correct order
                print(f"    DEBUG: Found coordinates for first pole: {latitude}, {longitude}")
                project_address = get_address_from_coords(latitude, longitude)
                print(f"    DEBUG: Found address from coordinates: {project_address}")
            else:
                print("    DEBUG: No geographic coordinates found for first pole")

            # Find designs and extract loading
            for design in loc.get('designs', []):
                if not isinstance(design, dict):
                    continue
                design_label = design.get('label', '').lower()
                
                # Extract actual stress percentage from analysis array
                analysis_list = design.get('analysis', [])
                if not isinstance(analysis_list, list):
                    print(f"    DEBUG: No analysis list found for design '{design.get('label', '')}'")
                    continue
                
                # Collect all STRESS/PERCENT values and pick the maximum
                stress_values = []
                for design_case in analysis_list:
                    if not isinstance(design_case, dict):
                        continue
                    results = design_case.get('results', [])
                    if not isinstance(results, list):
                        continue
                    
                    for result in results:
                        if (isinstance(result, dict)
                            and result.get('analysisType', '').upper() == 'STRESS'
                            and result.get('unit', '').upper() == 'PERCENT'):
                            val = result.get('actual', 0.0)
                            stress_values.append(val)
                            print(f"    DEBUG: candidate STRESS = {val:.1f}%")
                
                if not stress_values:
                    print(f"    DEBUG: No STRESS/PERCENT found for '{design.get('label', '')}'")
                    continue
                
                # Take the worst-case (maximum stress)
                stress_pct = max(stress_values)
                print(f"    DEBUG: using max STRESS = {stress_pct:.1f}% for design '{design.get('label', '')}')")
                
                # Determine if this is existing or final design based on actual labels
                if design_label == 'measured design' or 'measured' in design_label or 'existing' in design_label:
                    existing_loading = stress_pct
                    print(f"    DEBUG: Set existing_loading = {existing_loading:.1f}% for design '{design.get('label', '')}'")
                elif design_label == 'recommended design' or 'recommended' in design_label or 'final' in design_label or 'proposed' in design_label:
                    final_loading = stress_pct
                    print(f"    DEBUG: Set final_loading = {final_loading:.1f}% for design '{design.get('label', '')}'")
                else:
                    # If no clear indicator, treat first design as existing, subsequent as final
                    if existing_loading is None:
                        existing_loading = stress_pct
                        print(f"    DEBUG: Set existing_loading = {existing_loading:.1f}% for first design '{design.get('label', '')}'")
                    else:
                        final_loading = stress_pct
                        print(f"    DEBUG: Set final_loading = {final_loading:.1f}% for subsequent design '{design.get('label', '')}')")

            # Count PLAs (Power Line Attachments) if present
            if 'attachments' in loc:
                attachments = loc['attachments']
                if isinstance(attachments, list):
                    total_plas += len(attachments)

            # Extract just the numbers after the pole prefix (e.g., "1-PL410620" -> "410620")
            formatted_pole_id = pole_id
            if pole_id:
                # Look for pattern like "1-PL" followed by numbers
                import re
                match = re.search(r'\d+-PL(\d+)', pole_id)
                if match:
                    formatted_pole_id = match.group(1)
            
            poles.append({
                'SCID': len(poles) + 1,  # Sequential counter starting from 1
                'Station ID': formatted_pole_id,
                'Address': project_address if len(poles) == 0 else '',  # Only include address for first pole
                'Existing Loading %': existing_loading,
                'Final Loading %': final_loading,
                'Notes': notes
            })

    # After loop completion, if project_address determined, override location for output
    pole_count = len(unique_pole_ids)
    comments = f"{total_plas} PLAs on {pole_count} poles"

    # Use project_address (from first pole's coordinates) as Location if available
    if project_address:
        location = project_address

    return {
        'Job Number': job_number,
        'Client': 'Charter/Spectrum',
        'Date': date,
        'Location': location,
        'City': city,
        'Engineer': engineer,
        'Comments': comments,
        'Poles': poles
    }


def print_cover_sheet(data: Dict[str, Any]):
    # Show only the Pole Data Summary
    print("=" * 110)  # Increased width to accommodate Address column
    print("POLE DATA SUMMARY")
    print("=" * 110)
    print(f"{'SCID':<6} {'Station ID':<15} {'Address':<25} {'Existing Loading %':<20} {'Final Loading %':<20} {'Notes':<20}")
    print("-" * 110)
    for pole in data['Poles']:
        existing = f"{pole['Existing Loading %']:.1f}%" if pole['Existing Loading %'] is not None else "N/A"
        final = f"{pole['Final Loading %']:.1f}%" if pole['Final Loading %'] is not None else "N/A"
        print(f"{pole['SCID']:<6} {pole['Station ID']:<15} {pole['Address']:<25} {existing:<20} {final:<20} {pole['Notes']:<20}")
    print("=" * 110)


def main():
    parser = argparse.ArgumentParser(description='CPS Delivery Tool - Cover Sheet Tool')
    parser.add_argument('spida_file', help='Path to SPIDAcalc JSON file')
    args = parser.parse_args()

    if not Path(args.spida_file).exists():
        print(f"Error: SPIDAcalc file not found: {args.spida_file}")
        return

    with open(args.spida_file, 'r', encoding='utf-8') as f:
        try:
            json_data = json.load(f)
        except Exception as e:
            print(f"Error reading JSON: {e}")
            return

    debug_design_labels(json_data)
    cover_sheet_data = extract_cover_sheet_data(json_data)
    print_cover_sheet(cover_sheet_data)


if __name__ == "__main__":
    main() 