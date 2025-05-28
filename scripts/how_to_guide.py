#!/usr/bin/env python3
"""
CPS Delivery Tool - How To Guide
Python equivalent of the React HowToGuide.tsx page

This script provides comprehensive documentation and usage instructions
for the CPS delivery tools, including the Pole Comparison Tool and Cover Sheet Tool.
"""

import argparse
import sys
from datetime import datetime


class HowToGuide:
    """Documentation and guide for CPS delivery tools"""
    
    def __init__(self):
        self.current_year = datetime.now().year
    
    def print_header(self):
        """Print the application header"""
        print("=" * 80)
        print("CPS DELIVERY TOOL - HOW TO GUIDE")
        print("=" * 80)
        print()
    
    def print_footer(self):
        """Print the application footer"""
        print()
        print("=" * 80)
        print(f"CPS Delivery Tool © {self.current_year}")
        print("=" * 80)
    
    def show_pole_comparison_guide(self):
        """Display the pole comparison tool guide"""
        print("POLE COMPARISON TOOL")
        print("=" * 40)
        print()
        
        print("OVERVIEW")
        print("-" * 20)
        print("The Pole Comparison Tool allows you to compare pole data between Katapult")
        print("and SPIDAcalc files to identify discrepancies and ensure consistency.")
        print()
        
        print("HOW TO USE")
        print("-" * 20)
        print("1. Prepare a Katapult Excel file and a SPIDAcalc JSON file")
        print("2. Run the tool with the following command:")
        print("   python pole_comparison_tool.py <katapult_file> <spida_file>")
        print("3. Set your desired threshold for identifying issues (default is 5%):")
        print("   python pole_comparison_tool.py <katapult_file> <spida_file> --threshold 10.0")
        print("4. View the results in the console output")
        print("5. Export the results to CSV if needed:")
        print("   python pole_comparison_tool.py <katapult_file> <spida_file> --export results.csv")
        print("6. Export only poles with issues:")
        print("   python pole_comparison_tool.py <katapult_file> <spida_file> --export issues.csv --export-issues-only")
        print()
        
        print("COMMAND LINE OPTIONS")
        print("-" * 20)
        print("Required arguments:")
        print("  katapult_file    Path to Katapult Excel file")
        print("  spida_file       Path to SPIDAcalc JSON file")
        print()
        print("Optional arguments:")
        print("  --threshold FLOAT      Threshold for identifying loading issues (default: 5.0)")
        print("  --export FILENAME      Export results to CSV file")
        print("  --export-issues-only   Export only poles with issues")
        print("  --help                 Show help message")
        print()
        
        print("LOGIC BEHIND THE TOOL")
        print("-" * 20)
        print()
        
        print("File Processing:")
        print("• Katapult Excel File: Contains pole data exported from Katapult, including")
        print("  pole IDs, specifications, and loading percentages.")
        print("• SPIDAcalc JSON File: Contains pole data exported from SPIDAcalc, with a")
        print("  different structure but similar information.")
        print()
        
        print("Data Extraction:")
        print("For each file, the tool extracts the following key information:")
        print("• Pole IDs: Unique identifiers for each pole, normalized for consistent comparison.")
        print("• Pole Specifications: The physical characteristics of each pole (height, class, material).")
        print("• Existing Loading: The current load percentage on each pole.")
        print("• Final Loading: The projected load percentage after proposed changes.")
        print()
        
        print("Matching Algorithm:")
        print("The tool uses a sophisticated matching algorithm to pair poles between the two systems:")
        print("1. Normalizes pole IDs by removing special characters and standardizing format.")
        print("2. Extracts numeric portions of IDs for additional matching capability.")
        print("3. Attempts to match poles using both full normalized IDs and numeric-only portions.")
        print("4. Identifies poles that exist in one system but not the other.")
        print()
        
        print("Issue Detection:")
        print("The tool identifies several types of issues:")
        print("• Pole Specification Mismatches: When the same pole has different specifications")
        print("  in each system.")
        print("• Loading Discrepancies: When the loading percentages differ by more than the")
        print("  specified threshold.")
        print("• Missing Poles: Poles that exist in one system but not the other.")
        print("• Formatting Issues: Inconsistencies in how pole IDs are formatted between systems.")
        print()
        
        print("TROUBLESHOOTING")
        print("-" * 20)
        print()
        
        print("Common Issues:")
        print()
        print("• No data appears after processing:")
        print("  Ensure your files contain the expected data structure. The Katapult file should")
        print("  be an Excel spreadsheet with columns for pole IDs, specifications, and loading")
        print("  percentages. The SPIDAcalc file should be a JSON export with the standard structure.")
        print()
        print("• Many missing poles reported:")
        print("  This often indicates a formatting difference in pole IDs between systems. Check")
        print("  how poles are identified in each system and ensure consistency.")
        print()
        print("• Loading percentages seem incorrect:")
        print("  Verify that the correct columns are being used from the Katapult file. For")
        print("  SPIDAcalc, ensure that the correct analysis results are being referenced.")
        print()
        
        print("Expected File Formats:")
        print()
        print("Katapult Excel File should contain columns such as:")
        print("• pole_tag or Pole Tag (pole identifier)")
        print("• scid or SCID (SCID number)")
        print("• existing_capacity_% (existing loading percentage)")
        print("• final_passing_capacity_% (final loading percentage)")
        print("• pole_height, pole_class, pole_species (pole specifications)")
        print()
        print("SPIDAcalc JSON File should contain:")
        print("• leads[].locations[].label (pole identifier)")
        print("• leads[].locations[].designs[].structure.pole (pole specifications)")
        print("• leads[].locations[].designs[].analysis.results (loading analysis)")
        print()
    
    def show_cover_sheet_guide(self):
        """Display the cover sheet tool guide"""
        print("COVER SHEET TOOL")
        print("=" * 40)
        print()
        
        print("OVERVIEW")
        print("-" * 20)
        print("The Cover Sheet Tool generates formatted cover sheets from SPIDAcalc files,")
        print("extracting key project information and pole data for documentation purposes.")
        print()
        
        print("HOW TO USE")
        print("-" * 20)
        print("1. Prepare a SPIDAcalc JSON file")
        print("2. Run the tool with the following command:")
        print("   python cover_sheet_tool.py <spida_file>")
        print("3. The tool will automatically extract project information and pole data")
        print("4. Review the extracted information in the console output")
        print("5. Copy the formatted cover sheet data for use in your documents")
        print()
        
        print("LOGIC BEHIND THE TOOL")
        print("-" * 20)
        print()
        
        print("File Processing:")
        print("The Cover Sheet Tool processes SPIDAcalc JSON files to extract project and pole information:")
        print("• Project Information: Job number, date, location, city, and engineer.")
        print("• Pole Data: Station IDs, existing and final loading percentages, and notes.")
        print()
        
        print("Data Extraction:")
        print("The tool extracts information from specific paths in the SPIDAcalc JSON structure:")
        print("• Job Number: Extracted from the 'label' field.")
        print("• Date: Extracted from the 'date' field and formatted as MM/DD/YYYY.")
        print("• Location: Extracted from 'clientData.generalLocation' or determined via geocoding.")
        print("• City: Extracted from 'address.city' or determined via geocoding.")
        print("• Engineer: Extracted from the 'engineer' field.")
        print("• Pole Data: Extracted from the 'leads.locations' structure.")
        print()
        
        print("Geocoding:")
        print("If location or city information is missing, the tool attempts to determine")
        print("this information using geocoding:")
        print("1. Extracts coordinates from the first pole in the file.")
        print("2. Uses a geocoding service to convert these coordinates to an address.")
        print("3. Extracts city and location information from the geocoded address.")
        print()
        
        print("Comments Generation:")
        print("The tool automatically generates a comment summarizing the project scope:")
        print("• Counts the total number of PLAs (Power Line Attachments) across all poles.")
        print("• Counts the number of unique poles in the project.")
        print("• Formats this information as '[PLA count] PLAs on [pole count] poles'.")
        print()
        
        print("TROUBLESHOOTING")
        print("-" * 20)
        print()
        
        print("Common Issues:")
        print()
        print("• Missing project information:")
        print("  If fields like job number or date are missing, check that your SPIDAcalc file")
        print("  contains this information in the expected fields.")
        print()
        print("• Missing pole data:")
        print("  Ensure your SPIDAcalc file contains the expected structure with leads, locations,")
        print("  and designs.")
        print()
        print("• Incorrect location or city:")
        print("  If geocoding fails, you may need to manually enter this information. Check that")
        print("  your SPIDAcalc file contains valid coordinates.")
        print()
    
    def show_installation_guide(self):
        """Display installation and setup guide"""
        print("INSTALLATION AND SETUP")
        print("=" * 40)
        print()
        
        print("REQUIREMENTS")
        print("-" * 20)
        print("• Python 3.7 or higher")
        print("• Required Python packages:")
        print("  - pandas (for Excel file processing)")
        print("  - openpyxl (for Excel file reading)")
        print("  - requests (for geocoding services)")
        print()
        
        print("INSTALLATION")
        print("-" * 20)
        print("1. Install Python 3.7+ from https://python.org")
        print("2. Install required packages:")
        print("   pip install pandas openpyxl requests")
        print("3. Download the CPS delivery tool scripts")
        print("4. Make scripts executable (Linux/Mac):")
        print("   chmod +x pole_comparison_tool.py")
        print("   chmod +x cover_sheet_tool.py")
        print("   chmod +x how_to_guide.py")
        print()
        
        print("USAGE EXAMPLES")
        print("-" * 20)
        print("Basic pole comparison:")
        print("  python pole_comparison_tool.py katapult_data.xlsx spida_data.json")
        print()
        print("Pole comparison with custom threshold:")
        print("  python pole_comparison_tool.py katapult_data.xlsx spida_data.json --threshold 10.0")
        print()
        print("Export results to CSV:")
        print("  python pole_comparison_tool.py katapult_data.xlsx spida_data.json --export results.csv")
        print()
        print("Export only issues:")
        print("  python pole_comparison_tool.py katapult_data.xlsx spida_data.json --export issues.csv --export-issues-only")
        print()
        print("Generate cover sheet:")
        print("  python cover_sheet_tool.py spida_data.json")
        print()
        print("Show this guide:")
        print("  python how_to_guide.py")
        print("  python how_to_guide.py --topic pole-comparison")
        print("  python how_to_guide.py --topic cover-sheet")
        print("  python how_to_guide.py --topic installation")
        print()
    
    def show_file_format_guide(self):
        """Display detailed file format specifications"""
        print("FILE FORMAT SPECIFICATIONS")
        print("=" * 40)
        print()
        
        print("KATAPULT EXCEL FILE FORMAT")
        print("-" * 30)
        print("The Katapult Excel file should be a standard .xlsx or .xls file with the following columns:")
        print()
        print("Required Columns:")
        print("• pole_tag or Pole Tag - Unique identifier for each pole")
        print("• existing_capacity_% - Current loading percentage (0-100)")
        print("• final_passing_capacity_% - Final loading percentage after changes (0-100)")
        print()
        print("Optional Columns:")
        print("• scid or SCID - SCID number for the pole")
        print("• PL_number - PL number for the pole")
        print("• pole_height - Height of the pole in feet")
        print("• pole_class - Class of the pole (1, 2, 3, etc.)")
        print("• pole_species - Wood species (e.g., 'Southern Pine', 'SP', 'SPC')")
        print()
        print("Notes:")
        print("• Column names are case-insensitive and flexible")
        print("• The tool will attempt to find columns with similar names")
        print("• Loading percentages can be in decimal (0.0-1.0) or percentage (0-100) format")
        print("• Species abbreviations 'SP' and 'SPC' will be expanded to 'Southern Pine'")
        print()
        
        print("SPIDACALC JSON FILE FORMAT")
        print("-" * 30)
        print("The SPIDAcalc JSON file should be a standard JSON export with the following structure:")
        print()
        print("Required Fields:")
        print("• label - Project/job identifier")
        print("• date - Project date (ISO format)")
        print("• leads[] - Array of project leads")
        print("  • locations[] - Array of pole locations")
        print("    • label - Pole identifier")
        print("    • designs[] - Array of pole designs")
        print("      • structure.pole - Pole specifications")
        print("      • analysis.results[] - Analysis results with loading percentages")
        print()
        print("Optional Fields:")
        print("• engineer - Engineer name")
        print("• address.city - Project city")
        print("• clientData.generalLocation - Project location")
        print("• clientData.poles[] - Pole specification definitions")
        print()
        print("Notes:")
        print("• The tool extracts pole specifications from the first design")
        print("• Loading percentages are taken from analysis results")
        print("• Missing location/city information will trigger geocoding attempts")
        print()
        
        print("OUTPUT FORMATS")
        print("-" * 20)
        print("CSV Export Format:")
        print("The exported CSV file contains the following columns:")
        print("• SCID # - SCID number")
        print("• SPIDA Pole Number - Pole ID from SPIDAcalc")
        print("• Katapult Pole Number - Pole ID from Katapult")
        print("• SPIDA Pole Spec - Pole specification from SPIDAcalc")
        print("• Katapult Pole Spec - Pole specification from Katapult")
        print("• SPIDA Existing Loading % - Existing loading from SPIDAcalc")
        print("• Katapult Existing Loading % - Existing loading from Katapult")
        print("• SPIDA Final Loading % - Final loading from SPIDAcalc")
        print("• Katapult Final Loading % - Final loading from Katapult")
        print("• Existing Δ - Difference in existing loading percentages")
        print("• Final Δ - Difference in final loading percentages")
        print()
    
    def show_all_guides(self):
        """Display all guides"""
        self.print_header()
        
        print("TABLE OF CONTENTS")
        print("=" * 40)
        print("1. Installation and Setup")
        print("2. Pole Comparison Tool")
        print("3. Cover Sheet Tool")
        print("4. File Format Specifications")
        print()
        print("Use --topic <topic> to view a specific section:")
        print("  --topic installation")
        print("  --topic pole-comparison")
        print("  --topic cover-sheet")
        print("  --topic file-formats")
        print()
        
        self.show_installation_guide()
        print("\n" + "="*80 + "\n")
        
        self.show_pole_comparison_guide()
        print("\n" + "="*80 + "\n")
        
        self.show_cover_sheet_guide()
        print("\n" + "="*80 + "\n")
        
        self.show_file_format_guide()
        
        self.print_footer()


def main():
    """Main function to display the how-to guide"""
    parser = argparse.ArgumentParser(description='CPS Delivery Tool - How To Guide')
    parser.add_argument('--topic', choices=['installation', 'pole-comparison', 'cover-sheet', 'file-formats'],
                       help='Show specific topic guide')
    
    args = parser.parse_args()
    
    guide = HowToGuide()
    
    if args.topic == 'installation':
        guide.print_header()
        guide.show_installation_guide()
        guide.print_footer()
    elif args.topic == 'pole-comparison':
        guide.print_header()
        guide.show_pole_comparison_guide()
        guide.print_footer()
    elif args.topic == 'cover-sheet':
        guide.print_header()
        guide.show_cover_sheet_guide()
        guide.print_footer()
    elif args.topic == 'file-formats':
        guide.print_header()
        guide.show_file_format_guide()
        guide.print_footer()
    else:
        guide.show_all_guides()


if __name__ == "__main__":
    main() 