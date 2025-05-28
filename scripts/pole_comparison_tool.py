#!/usr/bin/env python3
"""
CPS Delivery Tool - Pole Comparison Tool
Python equivalent of the React Index.tsx page

This tool compares pole data between Katapult Excel files and SPIDAcalc JSON files
to identify discrepancies and ensure consistency.
"""

import json
import pandas as pd
import re
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import requests

# Allowed node types from Katapult to include in comparison (case-insensitive)
ALLOWED_NODE_TYPES = {
    "pole",
    "power",
    "power transformer",
    "joint",
    "joint transformer",
}

@dataclass
class ProcessedRow:
    """Data structure for processed pole comparison results"""
    pole_number: str
    scid_number: str
    spida_pole_number: str
    katapult_pole_number: str
    spida_pole_spec: str
    katapult_pole_spec: str
    spida_existing_loading: float
    katapult_existing_loading: float
    spida_final_loading: float
    katapult_final_loading: float
    existing_delta: Optional[float] = None
    final_delta: Optional[float] = None
    has_issue: Optional[bool] = None


@dataclass
class VerificationResult:
    """Data structure for pole number verification results"""
    missing_in_spida: List[str]
    missing_in_katapult: List[str]
    duplicates_in_spida: List[str]
    duplicates_in_katapult: List[str]
    formatting_issues: List[Dict[str, str]]


@dataclass
class KatapultPole:
    """Data structure for Katapult pole data"""
    pole_id: str
    normalized_pole_id: str
    numeric_id: str
    pole_spec: str
    existing_loading: float
    final_loading: float
    scid: Optional[str] = None
    pl_number: Optional[str] = None


@dataclass
class SpidaPole:
    """Data structure for SPIDAcalc pole data"""
    pole_id: str
    normalized_pole_id: str
    numeric_id: str
    location_number: str
    pole_spec: str
    existing_loading: float
    final_loading: float
    order: int  # order of appearance in the SPIDA file
    passes_final: bool = True  # whether recommended design passes, used for formatting


class PoleComparisonTool:
    """Main class for pole comparison functionality"""
    
    def __init__(self, threshold: float = 5.0):
        self.threshold = threshold
        
    def normalize_pole_id(self, pole_id: str) -> str:
        """Normalize pole ID for consistent comparison"""
        if not pole_id:
            return ''
        
        normalized = str(pole_id).strip().lower()
        normalized = re.sub(r'\s+', '', normalized)  # Remove all whitespace
        normalized = re.sub(r'[^a-z0-9-]', '', normalized)  # Remove special chars except hyphen
        
        return normalized
    
    def extract_numeric_id(self, pole_id: str) -> str:
        """Extract numeric portion from pole ID to aid matching.

        Strategy (prioritized):
        1. If the ID contains a pattern like "PLXXXXX" (case-insensitive), return
           the digits that follow the "PL" – e.g. "145-PL461207" → "461207".
        2. Otherwise, grab the digits that appear after the last hyphen if any –
           e.g. "146-455194" → "455194".
        3. Fallback to all digits in the string (previous behaviour).
        """
        if not pole_id:
            return ''

        pole_str = str(pole_id)
        # 1) Digits after PL
        m = re.search(r'PL\s*-?\s*(\d+)', pole_str, re.IGNORECASE)
        if m:
            return m.group(1)

        # 2) Digits after last hyphen
        m = re.search(r'-\s*(\d+)\s*$', pole_str)
        if m:
            return m.group(1)

        # 3) Fallback: all digits
        numeric_chars = re.findall(r'\d', pole_str)
        return ''.join(numeric_chars)
    
    def get_field_value(self, obj: Dict[str, Any], field_options: List[str], debug_label: str = None) -> Any:
        """Case-insensitive object property access with fallback options"""
        if not obj:
            return None
        
        # Try each field option in order
        for field in field_options:
            # Try exact match
            if field in obj and obj[field] is not None:
                if debug_label:
                    print(f"Found {debug_label} using exact match for field '{field}': {obj[field]}")
                return obj[field]
            
            # Try case-insensitive match
            lower_field = field.lower()
            for key in obj.keys():
                if key.lower() == lower_field and obj[key] is not None:
                    if debug_label:
                        print(f"Found {debug_label} using case-insensitive match for field '{field}' -> '{key}': {obj[key]}")
                    return obj[key]
            
            # Try fuzzy matches - looking for fields that contain the key term
            fuzzy_matches = [key for key in obj.keys() 
                           if lower_field in key.lower() or key.lower() in lower_field]
            
            if fuzzy_matches:
                fuzzy_match = fuzzy_matches[0]  # Take the first fuzzy match
                if debug_label:
                    print(f"Found {debug_label} using fuzzy match for '{field}' -> '{fuzzy_match}': {obj[fuzzy_match]}")
                return obj[fuzzy_match]
        
        if debug_label:
            print(f"Could not find {debug_label} using any of these fields: {', '.join(field_options)}")
        
        return None
    
    def _to_float_safe(self, value: Any) -> float:
        """Convert various raw representations (str, int, float, dict) to float.
        If conversion fails the function returns 0.0.
        For dict values it tries common numeric sub-keys like 'value' or
        'percent'."""
        try:
            if value is None:
                return 0.0
            # Numbers
            if isinstance(value, (int, float)):
                return float(value)
            # Strings – strip everything except digits / dot / minus
            if isinstance(value, str):
                cleaned = re.sub(r"[^0-9.\-]", "", value)
                return float(cleaned) if cleaned else 0.0
            # Dicts – look for typical keys
            if isinstance(value, dict):
                for key in ("value", "percent", "percentage", "%", "load", "loading"):
                    if key in value:
                        return self._to_float_safe(value[key])
                # Fallback: try first element if dict has single item
                if len(value) == 1:
                    return self._to_float_safe(next(iter(value.values())))
        except (ValueError, TypeError):
            pass
        return 0.0
    
    def extract_katapult_poles(self, excel_data: List[Dict[str, Any]]) -> Dict[str, KatapultPole]:
        """Extract pole data from Katapult Excel file"""
        poles = {}
        duplicates = set()
        
        print("Starting Katapult pole extraction...")
        
        # Define field options for different data points
        pole_id_options = [
            'pole_tag', 'Pole Tag', 'POLE_TAG', 'PoleTag',
            'pole_id', 'Pole ID', 'POLE_ID', 'PoleID',
            'pole_number', 'Pole Number', 'POLE_NUMBER', 'PoleNumber',
            'tag', 'Tag', 'TAG', 'id', 'ID', 'Id'
        ]
        
        scid_options = [
            'scid', 'SCID', 'Scid', 'scid_number', 'SCID_NUMBER',
            'scid number', 'SCID Number', 'scidnumber', 'SCIDNumber'
        ]
        
        pl_number_options = [
            'PL_number', 'PL Number', 'PL_NUMBER', 'PLNumber',
            'pl_number', 'pl number', 'plnumber', 'pl_num'
        ]
        
        # Pole specification component options
        pole_height_options = [
            'pole_height', 'Pole Height', 'POLE_HEIGHT', 'PoleHeight',
            'height', 'Height', 'HEIGHT', 'pole height', 'pole_h', 'pole h',
            'poleheight', 'pole-height', 'h', 'H', 'height_ft', 'heightft',
            'height_feet', 'heightfeet', 'length', 'Length', 'LENGTH', 'pole_length'
        ]
        
        pole_class_options = [
            'pole_class', 'Pole Class', 'POLE_CLASS', 'PoleClass',
            'class', 'Class', 'CLASS', 'class_of_pole', 'pole class',
            'pole_c', 'pole c', 'poleclass', 'pole-class', 'c', 'C',
            'class_number', 'class_no', 'classno', 'classnumber', 'strength', 'strength_class'
        ]
        
        pole_species_options = [
            'pole_species', 'Pole Species', 'POLE_SPECIES', 'PoleSpecies',
            'species', 'Species', 'SPECIES', 'wood_species', 'Wood Species',
            'WOOD_SPECIES', 'WoodSpecies', 'species_type', 'SpeciesType',
            'species_name', 'wood type', 'Wood Type', 'wood', 'Wood', 'WOOD',
            'timber_type', 'timber', 'material', 'Material', 'wood_type',
            'wood kind', 'pole_material', 'pole_wood_type', 'pole_wood',
            'wood_kind', 'birthmark_brand::pole_species*', 'birthmark_brand::pole_species',
            'birthmark_brand::species', 'pole_species*'
        ]
        
        existing_loading_options = [
            'existing_capacity_%', 'Existing Capacity %', 'existing_capacity',
            'Existing Capacity', 'existing capacity %', 'existing_capacity_percent',
            'existing capacity percent'
        ]
        
        final_loading_options = [
            'final_passing_capacity_%', 'Final Passing Capacity %',
            'final_passing_capacity', 'Final Passing Capacity',
            'final passing capacity %', 'final_passing_capacity_percent',
            'final passing capacity percent'
        ]
        
        node_type_options = ['node_type', 'Node Type', 'NODE_TYPE']
        dloc_options = ['DLOC_number', 'DLOC Number', 'dloc_number', 'DLOCNumber', 'dlocnum', 'dloc']
        
        for index, row in enumerate(excel_data):
            # Filter by node_type – include only allowed categories
            node_type_val = self.get_field_value(row, node_type_options)
            if node_type_val:
                node_type_clean = str(node_type_val).strip().lower()
                if node_type_clean not in ALLOWED_NODE_TYPES:
                    continue
            # Get pole ID
            # Try SCID + DLOC combination first
            scid_val = self.get_field_value(row, scid_options, 'SCID')
            dloc_val = self.get_field_value(row, dloc_options, 'DLOC number')
            pole_id = None
            if scid_val and dloc_val:
                pole_id = f"{scid_val}-{dloc_val}"
            if not pole_id:
                pole_id = self.get_field_value(row, pole_id_options, 'pole ID')
                if not pole_id and dloc_val:
                    pole_id = str(dloc_val)
            if not pole_id:
                print(f"Row {index}: No pole ID found, skipping")
                continue
            
            pole_id = str(pole_id).strip()
            normalized_pole_id = self.normalize_pole_id(pole_id)
            
            # Skip if already processed this pole ID
            if normalized_pole_id in poles:
                duplicates.add(normalized_pole_id)
                print(f"Duplicate pole ID found: {pole_id}")
                continue
            
            # Get SCID and PL number
            scid = scid_val  # already fetched above
            pl_number = self.get_field_value(row, pl_number_options, 'PL number')
            
            # Build pole specification
            pole_height = self.get_field_value(row, pole_height_options, 'pole height')
            pole_class = self.get_field_value(row, pole_class_options, 'pole class')
            pole_species = self.get_field_value(row, pole_species_options, 'pole species')
            
            print(f"Row {index}: Raw pole details - Height: {pole_height}, Class: {pole_class}, Species: {pole_species}")
            
            # Parse and clean height value
            height_value = ''
            if pole_height:
                if isinstance(pole_height, str):
                    height_match = re.search(r'(\d+)', pole_height)
                    height_value = height_match.group(1) if height_match else pole_height
                else:
                    height_value = str(pole_height)
            
            # Parse and clean class value
            class_value = ''
            if pole_class:
                if isinstance(pole_class, str):
                    class_match = re.search(r'(\w+)', pole_class)
                    class_value = class_match.group(1) if class_match else pole_class
                else:
                    class_value = str(pole_class)
            
            # Clean and format species value
            species_value = ''
            if pole_species:
                if isinstance(pole_species, str):
                    species_value = pole_species.strip()
                    
                    # Handle species abbreviations
                    if species_value.upper() in ['SPC', 'SP']:
                        species_value = 'Southern Pine'
                        print(f"Row {index}: Expanded species abbreviation '{pole_species}' to 'Southern Pine'")
                    else:
                        # Capitalize first letter of each word in species
                        species_value = ' '.join(word.capitalize() for word in species_value.split())
                else:
                    species_value = str(pole_species)
                    if species_value.upper() in ['SPC', 'SP']:
                        species_value = 'Southern Pine'
                        print(f"Row {index}: Expanded species code '{pole_species}' to 'Southern Pine'")
            
            # Format based on available components: "[height]-[class] [species]"
            pole_spec = ""
            if height_value and class_value:
                pole_spec = f"{height_value}-{class_value}"
                if species_value:
                    pole_spec += f" {species_value}"
                print(f"Row {index}: Created full pole spec: {pole_spec}")
            elif height_value:
                pole_spec = height_value
                if species_value:
                    pole_spec += f" {species_value}"
                print(f"Row {index}: Created pole spec with height{' and species' if species_value else ''}: {pole_spec}")
            elif class_value:
                pole_spec = class_value
                if species_value:
                    pole_spec += f" {species_value}"
                print(f"Row {index}: Created pole spec with class{' and species' if species_value else ''}: {pole_spec}")
            elif species_value:
                pole_spec = species_value
                print(f"Row {index}: Created pole spec with only species: {pole_spec}")
            else:
                pole_spec = "Unknown"
                print(f"Row {index}: No pole spec information found, using 'Unknown'")
            
            # Get loading values
            existing_loading_raw = self.get_field_value(row, existing_loading_options, 'existing loading')
            final_loading_raw = self.get_field_value(row, final_loading_options, 'final loading')
            
            print(f"Row {index} raw loading values - Existing: {existing_loading_raw}, Final: {final_loading_raw}")
            
            # Parse loading values
            existing_loading = self._to_float_safe(existing_loading_raw)
            final_loading = self._to_float_safe(final_loading_raw)
            
            # Check for values that might be percentages expressed as 0-1 values instead of 0-100
            if 0 < existing_loading < 1:
                existing_loading *= 100
                print(f"Row {index}: Converted existingLoading from decimal to percentage: {existing_loading}")
            
            if 0 < final_loading < 1:
                final_loading *= 100
                print(f"Row {index}: Converted finalLoading from decimal to percentage: {final_loading}")
            
            print(f"Row {index} parsed loading values - Existing: {existing_loading}, Final: {final_loading}")
            
            # Extract numeric ID from pole number for matching
            numeric_id = self.extract_numeric_id(pole_id)
            
            # Create pole object
            pole = KatapultPole(
                pole_id=pole_id,
                normalized_pole_id=normalized_pole_id,
                numeric_id=numeric_id,
                pole_spec=pole_spec,
                existing_loading=existing_loading,
                final_loading=final_loading,
                scid=str(scid) if scid else None,
                pl_number=str(pl_number) if pl_number else None
            )
            
            poles[normalized_pole_id] = pole
            print(f"Added Katapult pole: {pole_id} -> {normalized_pole_id}")
        
        print(f"Extracted {len(poles)} Katapult poles")
        return poles
    
    def extract_pole_specification(self, design: Dict[str, Any]) -> str:
        """Extract SPIDAcalc pole specification from design"""
        # Retrieve the 'structure' portion – ensure it is a dictionary
        structure = design.get('structure')
        if not isinstance(structure, dict):
            print("  Warning: 'structure' field is not a dict; skipping spec extraction")
            return "Unknown"

        # Extract the 'pole' sub-dict – ensure it is a dictionary
        pole = structure.get('pole')
        if not isinstance(pole, dict):
            print("  Warning: 'pole' field is not a dict; skipping spec extraction")
            return "Unknown"
        
        # Get the class of pole from clientItem.classOfPole
        class_of_pole = "Unknown"
        if pole.get('clientItem', {}).get('classOfPole'):
            class_of_pole = pole['clientItem']['classOfPole']
        
        # Get the height
        height_in_feet = 0
        if pole.get('clientItem', {}).get('height', {}).get('value'):
            height_in_meters = pole['clientItem']['height']['value']
            height_in_feet = round(height_in_meters * 3.28084)
        
        # Get the species
        species = ""
        
        # Try multiple sources to find species
        if pole.get('clientItem', {}).get('species'):
            species = pole['clientItem']['species']
        elif design.get('clientData', {}).get('poles'):
            # Find the pole definition that matches this pole's class
            poles_data = design['clientData']['poles']
            if isinstance(poles_data, list):
                pole_definition = next(
                    (p for p in poles_data if p.get('classOfPole') == class_of_pole),
                    None
                )
                if pole_definition and pole_definition.get('species'):
                    species = pole_definition['species']
        
        # Clean up species value if found
        if species:
            species = species.strip()
            # Capitalize first letter of each word in species
            species = ' '.join(word.capitalize() for word in species.split())
        
        # Format pole specification based on available information
        if height_in_feet > 0 and class_of_pole != "Unknown":
            # Create the [height]-[class] format
            base_spec = f"{height_in_feet}-{class_of_pole}"
            # Append species if available
            return f"{base_spec} {species}" if species else base_spec
        elif height_in_feet > 0:
            return f"{height_in_feet} {species}" if species else str(height_in_feet)
        elif class_of_pole != "Unknown":
            return f"{class_of_pole} {species}" if species else class_of_pole
        elif species:
            return species
        else:
            return "Unknown"
    
    def extract_spida_poles(self, json_data: Dict[str, Any]) -> Dict[str, SpidaPole]:
        """Extract pole data from SPIDAcalc JSON file"""
        # Handle cases where the root of the JSON document is a list instead of
        # the expected object with a top-level "leads" key.  In these exports
        # the list itself contains the lead objects, so we can simply wrap it in
        # a dictionary to reuse the existing parsing logic.
        if isinstance(json_data, list):
            json_data = {"leads": json_data}
        
        poles = {}
        duplicates = set()
        order_counter = 0  # track original order of appearance
        
        print("Starting SPIDAcalc pole extraction...")
        
        # Process each lead > location > design path
        if isinstance(json_data, dict) and json_data.get('leads') and isinstance(json_data['leads'], list):
            print(f"Found {len(json_data['leads'])} leads in SPIDAcalc data")
            
            for lead_index, lead in enumerate(json_data['leads']):
                # Ensure the lead element is a dict
                if not isinstance(lead, dict):
                    print(f"Skipping non-dict lead at index {lead_index}: {lead!r}")
                    continue

                if lead.get('locations') and isinstance(lead['locations'], list):
                    print(f"Lead {lead_index}: Found {len(lead['locations'])} locations")
                    
                    for loc_index, loc in enumerate(lead['locations']):
                        # Ensure the location element is a dict
                        if not isinstance(loc, dict):
                            print(f"Skipping non-dict location at {lead_index}/{loc_index}: {loc!r}")
                            continue
                        # Use location.label for pole ID
                        if not loc.get('label'):
                            print(f"Location {loc_index} in Lead {lead_index} skipped: No label found")
                            continue
                        
                        pole_id = loc['label']
                        normalized_pole_id = self.normalize_pole_id(pole_id)
                        
                        print(f"Processing pole: {pole_id}, normalized: {normalized_pole_id}")
                        
                        # Skip if already processed this pole ID
                        if normalized_pole_id in poles:
                            duplicates.add(normalized_pole_id)
                            print(f"Duplicate pole ID found: {pole_id}")
                            continue
                        
                        # Initialize pole data
                        pole_spec = "Unknown"
                        existing_loading = 0.0
                        final_loading = 0.0
                        
                        # Process designs to find existing and final loading
                        if loc.get('designs') and isinstance(loc['designs'], list):
                            designs = loc['designs']
                            print(f"  Found {len(designs)} designs for pole {pole_id}")

                            # Identify measured and recommended designs
                            measured_design = next((d for d in designs if isinstance(d, dict) and d.get('label','').lower().startswith('measured')), None)
                            recommended_design = next((d for d in designs if isinstance(d, dict) and 'recommended' in d.get('label','').lower()), None)

                            # Fallbacks if not found
                            if measured_design is None and designs:
                                measured_design = designs[0]
                            if recommended_design is None and len(designs) > 1:
                                recommended_design = designs[1]

                            # Extract pole spec from recommended_design (or first design)
                            if recommended_design:
                                pole_spec = self.extract_pole_specification(recommended_design)
                                print(f"  Extracted pole spec: {pole_spec}")

                            def max_loading_from_design(design):
                                if not isinstance(design, dict):
                                    return 0.0, True
                                analysis = design.get('analysis')
                                if not (isinstance(analysis, list) or isinstance(analysis, dict)):
                                    return 0.0, True

                                # Ensure we iterate over list of analysis cases
                                cases = analysis if isinstance(analysis, list) else analysis.get('results', [])
                                max_percent = 0.0
                                passes_flag = True
                                # For each case, iterate its results array
                                for ac in cases:
                                    res_list = ac.get('results') if isinstance(ac, dict) else None
                                    if not isinstance(res_list, list):
                                        continue
                                    for result in res_list:
                                        if not isinstance(result, dict):
                                            continue
                                        if result.get('component') == 'Pole' and result.get('analysisType') == 'STRESS':
                                            percent = result.get('actual') or result.get('summary', {}).get('loadingPercent', 0.0)
                                            if percent is None:
                                                continue
                                            if percent > max_percent:
                                                max_percent = percent
                                                passes_flag = result.get('passes', True)
                                return max_percent, passes_flag

                            # Existing loading (measured)
                            existing_loading, _ = max_loading_from_design(measured_design)
                            print(f"  Set existing loading: {existing_loading}%")

                            # Final loading (recommended)
                            final_loading, passes_final = max_loading_from_design(recommended_design)
                            print(f"  Set final loading: {final_loading}% - passes={passes_final}")
                        
                        # Extract numeric ID from pole number for matching
                        numeric_id = self.extract_numeric_id(pole_id)
                        
                        # Get location number (SCID) from the pole ID or location data
                        location_number = loc.get('id', pole_id)
                        
                        # Create pole object
                        pole = SpidaPole(
                            pole_id=pole_id,
                            normalized_pole_id=normalized_pole_id,
                            numeric_id=numeric_id,
                            location_number=str(location_number),
                            pole_spec=pole_spec,
                            existing_loading=existing_loading,
                            final_loading=final_loading,
                            order=order_counter,
                            passes_final=passes_final
                        )
                        
                        poles[normalized_pole_id] = pole
                        print(f"Added SPIDAcalc pole: {pole_id} -> {normalized_pole_id}")
                        order_counter += 1  # increment after adding pole
        
        print(f"Extracted {len(poles)} SPIDAcalc poles")
        return poles
    
    def verify_pole_numbers(self, katapult_poles: Dict[str, KatapultPole], 
                           spida_poles: Dict[str, SpidaPole]) -> VerificationResult:
        """Verify pole numbers between Katapult and SPIDAcalc data"""
        result = VerificationResult(
            missing_in_spida=[],
            missing_in_katapult=[],
            duplicates_in_spida=[],
            duplicates_in_katapult=[],
            formatting_issues=[]
        )
        
        # Create maps for numeric ID lookup
        spida_numeric_map = {}
        katapult_numeric_map = {}
        
        # Build numeric ID maps
        for pole in spida_poles.values():
            if pole.numeric_id:
                spida_numeric_map[pole.numeric_id] = pole
        
        for pole in katapult_poles.values():
            if pole.numeric_id:
                katapult_numeric_map[pole.numeric_id] = pole
        
        print(f"Built numeric ID maps - SPIDA: {len(spida_numeric_map)}, Katapult: {len(katapult_numeric_map)}")
        
        # Build normalized lookup for SPIDA poles
        spida_normalized_set = {p.normalized_pole_id for p in spida_poles.values()}

        for pole in katapult_poles.values():
            found_match = False
            if pole.numeric_id and pole.numeric_id in spida_numeric_map:
                found_match = True
                # Check for formatting issues
                spida_pole = spida_numeric_map[pole.numeric_id]
                if pole.pole_id != spida_pole.pole_id:
                    result.formatting_issues.append({
                        'poleId': pole.pole_id,
                        'issue': f'Format mismatch: Katapult "{pole.pole_id}" vs SPIDA "{spida_pole.pole_id}" (matched by numeric ID: {pole.numeric_id})'
                    })
            # Fallback to normalized pole id comparison
            elif pole.normalized_pole_id in spida_normalized_set:
                found_match = True

            if not found_match:
                result.missing_in_spida.append(pole.pole_id)
                print(f"Pole {pole.pole_id} not found in SPIDA data (numeric ID and normalized match failed)")

        # Find poles in SPIDA but not in Katapult using numeric IDs
        katapult_normalized_set = {p.normalized_pole_id for p in katapult_poles.values()}

        for pole in spida_poles.values():
            if pole.numeric_id and pole.numeric_id not in katapult_numeric_map and pole.normalized_pole_id not in katapult_normalized_set:
                result.missing_in_katapult.append(pole.pole_id)
                print(f"Pole {pole.pole_id} not found in Katapult data (numeric ID and normalized match failed)")
        
        return result
    
    def generate_comparison_data(self, katapult_poles: Dict[str, KatapultPole], 
                               spida_poles: Dict[str, SpidaPole]) -> List[ProcessedRow]:
        """Generate comparison data between Katapult and SPIDAcalc"""
        results = []
        
        # Create maps for numeric ID lookup
        spida_numeric_map = {}
        katapult_numeric_map = {}
        
        # Build numeric ID maps
        for pole in spida_poles.values():
            if pole.numeric_id:
                spida_numeric_map[pole.numeric_id] = pole
        
        # Build normalized pole id map for fallback matching
        spida_normalized_map = {p.normalized_pole_id: p for p in spida_poles.values()}
        
        # Process each Katapult pole to ensure species abbreviations are expanded
        for pole in katapult_poles.values():
            # Final check for species abbreviations in pole_spec
            if pole.pole_spec:
                # Expand any remaining SP or SPC to Southern Pine
                if re.search(r'\bSP\b', pole.pole_spec, re.IGNORECASE) or re.search(r'\bSPC\b', pole.pole_spec, re.IGNORECASE):
                    pole.pole_spec = re.sub(r'\bSP\b', "Southern Pine", pole.pole_spec, flags=re.IGNORECASE)
                    pole.pole_spec = re.sub(r'\bSPC\b', "Southern Pine", pole.pole_spec, flags=re.IGNORECASE)
                    print(f"Expanded species abbreviation in final output for pole {pole.pole_id}: {pole.pole_spec}")
            
            if pole.numeric_id:
                katapult_numeric_map[pole.numeric_id] = pole
        
        print(f"Built ID maps for comparison - SPIDA numeric: {len(spida_numeric_map)}, Katapult numeric: {len(katapult_numeric_map)}, SPIDA normalized: {len(spida_normalized_map)}")
        
        # Sort SPIDA poles by original order so SCID sequence follows file order
        ordered_spida_poles = sorted(spida_poles.values(), key=lambda p: p.order)

        for spida_pole in ordered_spida_poles:
            katapult_pole = None

            # 1) Numeric ID match
            if spida_pole.numeric_id and spida_pole.numeric_id in katapult_numeric_map:
                katapult_pole = katapult_numeric_map[spida_pole.numeric_id]
            else:
                # 2) Normalized fallback
                if spida_pole.normalized_pole_id in katapult_poles:
                    katapult_pole = katapult_poles[spida_pole.normalized_pole_id]

            if katapult_pole is None:
                continue  # unmatched – skip or could create placeholder

            # Create comparison row
            row = ProcessedRow(
                pole_number=katapult_pole.pole_id,
                scid_number=str(spida_pole.order + 1),
                spida_pole_number=spida_pole.pole_id,
                katapult_pole_number=katapult_pole.pole_id,
                spida_pole_spec=spida_pole.pole_spec,
                katapult_pole_spec=katapult_pole.pole_spec,
                spida_existing_loading=spida_pole.existing_loading,
                katapult_existing_loading=katapult_pole.existing_loading,
                spida_final_loading=spida_pole.final_loading,
                katapult_final_loading=katapult_pole.final_loading
            )
            
            results.append(row)
        
        print(f"Generated {len(results)} comparison rows")
        return results
    
    def read_katapult_json(self, file_path: str) -> List[Dict[str, Any]]:
        """Read a Katapult JSON export and return a list of row dictionaries
        compatible with extract_katapult_poles().

        The Katapult JSON format (API/GraphQL export) typically contains all
        pole nodes underneath a top-level "nodes" object where the keys are
        the node IDs and each value has an ``attributes`` dictionary holding
        the actual pole fields.  We flatten each pole's ``attributes`` dict so
        that the keys line up with the column names that
        ``extract_katapult_poles`` already knows how to interpret (e.g.
        ``pole_tag``, ``PoleNumber``, ``height``, etc.).
        """
        try:
            print(f"Reading Katapult JSON file: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as err:
            print(f"Error parsing Katapult JSON file: {err}")
            raise Exception(f"Error parsing Katapult JSON file: {err}")

        # Support both the modern top-level object with "nodes" and a plain
        # array of nodes just in case.
        if isinstance(data, dict):
            # Some exports store poles inside a top-level "nodes" field while
            # others may just have the attributes at the root already.
            nodes_obj = data.get("nodes", data)
        elif isinstance(data, list):
            nodes_obj = data
        else:
            print("Unsupported Katapult JSON root type – expected dict or list, got", type(data))
            raise Exception("Unsupported Katapult JSON structure")

        # Determine an iterator of node objects
        if isinstance(nodes_obj, dict):
            node_iter = nodes_obj.values()
        elif isinstance(nodes_obj, list):
            node_iter = nodes_obj
        else:
            node_iter = []

        rows: List[Dict[str, Any]] = []
        for node in node_iter:
            # Some exports wrap the attributes under "attributes" – fall back
            # to the node itself if not present.
            attrs = node.get("attributes", node)
            row: Dict[str, Any] = {}

            # Copy all attributes so existing extraction logic can find fields
            if isinstance(attrs, dict):
                row.update(attrs)

            # Ensure common fields are present under the names used by the
            # Excel reader so we don't have to update the extraction logic.
            pole_tag = self.get_field_value(attrs, [
                "PoleNumber", "pole_number", "pole_tag", "Pole Tag", "electric_pole_tag",
            ], "pole tag")
            if pole_tag is not None:
                row["pole_tag"] = pole_tag

            # SCID & PL number if available
            scid_val = self.get_field_value(attrs, ["scid", "SCID", "Scid"], "SCID")
            if scid_val is not None:
                row["scid"] = scid_val

            pl_val = self.get_field_value(attrs, ["PL_number", "PL Number", "pl_number"], "PL number")
            if pl_val is not None:
                row["PL_number"] = pl_val

            # Default loading percentages to None; they may not exist in the
            # Katapult JSON export.
            if "existing_capacity_%" not in row:
                row["existing_capacity_%"] = None
            if "final_passing_capacity_%" not in row:
                row["final_passing_capacity_%"] = None

            rows.append(row)

        print(f"Flattened {len(rows)} pole nodes from Katapult JSON")
        return rows

    def process_files(self, katapult_file: str, spida_file: str) -> Tuple[List[ProcessedRow], VerificationResult]:
        """Process the uploaded files and return the comparison data"""
        try:
            print("Starting file processing...")

            # Read the Katapult file (auto-detect JSON vs Excel)
            katapult_lower = katapult_file.lower()
            if katapult_lower.endswith(".json"):
                katapult_data = self.read_katapult_json(katapult_file)
            else:
                katapult_data = self.read_excel_file(katapult_file)

            # Read the SPIDAcalc JSON
            spida_data = self.read_json_file(spida_file)

            # Extract pole information from both sources
            katapult_poles = self.extract_katapult_poles(katapult_data)
            spida_poles = self.extract_spida_poles(spida_data)

            print(f"Katapult poles extracted: {len(katapult_poles)}")
            print(f"SPIDA poles extracted: {len(spida_poles)}")

            # Verify pole numbers between the two sources
            verification = self.verify_pole_numbers(katapult_poles, spida_poles)

            # Generate comparison data
            comparison_data = self.generate_comparison_data(katapult_poles, spida_poles)

            return comparison_data, verification

        except Exception as error:
            print(f"Error processing files: {error}")
            raise error
    
    def read_excel_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Read Excel file content"""
        try:
            print(f"Reading Excel file: {file_path}")
            
            # Read Excel file with pandas
            df = pd.read_excel(file_path)
            
            print(f"Excel data rows found: {len(df)}")
            
            if len(df) > 0:
                print(f"First row columns: {', '.join(df.columns.tolist())}")
                
                # Check for critical columns
                critical_columns = ['scid', 'pole_tag', 'DLOC_number', 'PL_number', 
                                  'existing_capacity_%', 'final_passing_capacity_%', 
                                  'pole_spec', 'proposed_pole_spec']
                
                print("Checking for critical columns:")
                for column in critical_columns:
                    found = any(col == column or col.lower() == column.lower() for col in df.columns)
                    print(f"  {column}: {'FOUND' if found else 'NOT FOUND'}")
                
                # Log the first 3 rows for debugging
                print("First 3 rows of data:")
                for i in range(min(3, len(df))):
                    row = df.iloc[i].to_dict()
                    print(f"Row {i}: {row}")
            
            # Convert to list of dictionaries
            return df.to_dict('records')
            
        except Exception as err:
            print(f"Error parsing Excel file: {err}")
            raise Exception(f"Error parsing Excel file: {err}")
    
    def read_json_file(self, file_path: str) -> Dict[str, Any]:
        """Read JSON file content"""
        try:
            print(f"Reading JSON file: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as file:
                json_data = json.load(file)
            
            print("JSON file successfully parsed")
            return json_data
            
        except Exception as err:
            print(f"Error parsing JSON file: {err}")
            raise Exception(f"Error parsing JSON file: {err}")
    
    def apply_threshold_and_find_issues(self, data: List[ProcessedRow]) -> List[ProcessedRow]:
        """Apply threshold to find issues in the comparison data"""
        issue_rows = []
        
        for row in data:
            existing_delta = abs(row.spida_existing_loading - row.katapult_existing_loading)
            final_delta = abs(row.spida_final_loading - row.katapult_final_loading)
            spec_mismatch = row.spida_pole_spec != row.katapult_pole_spec
            
            row.existing_delta = existing_delta
            row.final_delta = final_delta
            row.has_issue = existing_delta > self.threshold or final_delta > self.threshold or spec_mismatch
            
            if row.has_issue:
                issue_rows.append(row)
        
        return issue_rows
    
    def export_to_csv(self, data: List[ProcessedRow], filename: str = "pole_comparison_results.csv"):
        """Export results to CSV file"""
        if not data:
            print("Nothing to export - no data available")
            return
        
        # Create DataFrame from results
        df_data = []
        for row in data:
            df_data.append({
                'SCID #': row.scid_number,
                'SPIDA Pole Number': row.spida_pole_number,
                'Katapult Pole Number': row.katapult_pole_number,
                'SPIDA Pole Spec': row.spida_pole_spec,
                'Katapult Pole Spec': row.katapult_pole_spec,
                'SPIDA Existing Loading %': row.spida_existing_loading,
                'Katapult Existing Loading %': row.katapult_existing_loading,
                'SPIDA Final Loading %': row.spida_final_loading,
                'Katapult Final Loading %': row.katapult_final_loading,
                'Existing Δ': row.existing_delta,
                'Final Δ': row.final_delta
            })
        
        df = pd.DataFrame(df_data)
        df.to_csv(filename, index=False)
        print(f"Export complete - CSV file saved as: {filename}")
    
    def print_verification_issues(self, verification: VerificationResult):
        """Print verification issues to console"""
        total_issues = (len(verification.missing_in_spida) + 
                       len(verification.missing_in_katapult) + 
                       len(verification.formatting_issues))
        
        if total_issues > 0:
            print("\n" + "="*60)
            print("POLE NUMBER VERIFICATION ISSUES")
            print("="*60)
            
            if verification.missing_in_spida:
                print(f"\nPoles missing in SPIDA ({len(verification.missing_in_spida)}):")
                print(", ".join(verification.missing_in_spida[:10]))
                if len(verification.missing_in_spida) > 10:
                    print("...")
            
            if verification.missing_in_katapult:
                print(f"\nPoles missing in Katapult ({len(verification.missing_in_katapult)}):")
                print(", ".join(verification.missing_in_katapult[:10]))
                if len(verification.missing_in_katapult) > 10:
                    print("...")
            
            if verification.formatting_issues:
                print(f"\nFormatting issues ({len(verification.formatting_issues)}):")
                for i, issue in enumerate(verification.formatting_issues[:5]):
                    print(f"  {issue['poleId']}: {issue['issue']}")
                if len(verification.formatting_issues) > 5:
                    print("  ...")
            
            print(f"\nNote: These issues might impact comparison results. Consider resolving them for more accurate analysis.")
            print("="*60)
    
    def print_results_summary(self, all_data: List[ProcessedRow], issues: List[ProcessedRow]):
        """Print results summary to console"""
        print("\n" + "="*60)
        print("RESULTS SUMMARY")
        print("="*60)
        print(f"Total poles processed: {len(all_data)}")
        print(f"Poles with issues: {len(issues)}")
        print(f"Threshold used: {self.threshold}%")
        
        if issues:
            print(f"\nFirst 10 poles with issues:")
            print(f"{'Pole ID':<15} {'Existing Δ':<12} {'Final Δ':<10} {'Spec Match':<12}")
            print("-" * 60)
            for i, row in enumerate(issues[:10]):
                spec_match = "✓" if row.spida_pole_spec == row.katapult_pole_spec else "✗"
                print(f"{row.pole_number:<15} {row.existing_delta:<12.2f} {row.final_delta:<10.2f} {spec_match:<12}")
        
        print("="*60)


def main():
    """Main function to run the pole comparison tool"""
    parser = argparse.ArgumentParser(description='CPS Delivery Tool - Pole Comparison')
    parser.add_argument('katapult_file', help='Path to Katapult Excel file')
    parser.add_argument('spida_file', help='Path to SPIDAcalc JSON file')
    parser.add_argument('--threshold', type=float, default=5.0, 
                       help='Threshold for identifying loading issues (default: 5.0)')
    parser.add_argument('--export', type=str, 
                       help='Export results to CSV file (specify filename)')
    parser.add_argument('--export-issues-only', action='store_true',
                       help='Export only poles with issues')
    
    args = parser.parse_args()
    
    # Validate input files
    if not Path(args.katapult_file).exists():
        print(f"Error: Katapult file not found: {args.katapult_file}")
        sys.exit(1)
    
    if not Path(args.spida_file).exists():
        print(f"Error: SPIDAcalc file not found: {args.spida_file}")
        sys.exit(1)
    
    # Create tool instance
    tool = PoleComparisonTool(threshold=args.threshold)
    
    try:
        # Process files
        print("Processing files...")
        all_data, verification = tool.process_files(args.katapult_file, args.spida_file)
        
        # Apply threshold to find issues
        issues = tool.apply_threshold_and_find_issues(all_data)
        
        # Print verification issues
        tool.print_verification_issues(verification)
        
        # Print results summary
        tool.print_results_summary(all_data, issues)
        
        # Export to CSV if requested
        if args.export:
            export_data = issues if args.export_issues_only else all_data
            tool.export_to_csv(export_data, args.export)
        
        print(f"\nProcessing complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 