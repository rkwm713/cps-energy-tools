# CPS Energy Tools - Web Application

A modern web application for CPS Energy utility tools including pole comparison, cover sheet generation, and MRR processing.

## Features

- **Pole Comparison Tool**: Compare pole data between Katapult Excel files and SPIDAcalc JSON files
- **Cover Sheet Tool**: Generate formatted cover sheets from SPIDAcalc files
- **MRR Tool**: Process Job JSON and GeoJSON files (web interface + desktop GUI)
- **How To Guide**: Comprehensive documentation and troubleshooting

## Installation

1. **Install Python 3.7+** (if not already installed)

2. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Open your browser** and navigate to:
   ```
   http://localhost:5000
   ```

## Usage

### Web Interface
- Navigate to `http://localhost:5000` in your browser
- Select the tool you want to use from the home page
- Upload your files using drag-and-drop or file browser
- Process files and view/export results

### Desktop GUI (MRR Tool)
- For full MRR processing capabilities, use the "Launch Desktop GUI" option
- This provides complete Excel report generation and advanced data analysis

## File Support

- **Excel Files**: `.xlsx`, `.xls` (Katapult data)
- **JSON Files**: `.json` (SPIDAcalc and Job data)
- **GeoJSON Files**: `.json`, `.geojson` (Geographic data)
- **Maximum file size**: 50 MB per file

## Tools Overview

### Pole Comparison Tool
- Compares pole data between Katapult and SPIDAcalc systems
- Identifies loading discrepancies and specification mismatches
- Exports results to CSV format
- Configurable threshold for issue detection

### Cover Sheet Tool
- Extracts project information from SPIDAcalc files
- Generates formatted cover sheets for documentation
- Copy to clipboard or download as text file
- Visual project information cards

### MRR Tool
- **Web Interface**: Basic file validation and information extraction
- **Desktop GUI**: Full MRR processing with Excel report generation
- Processes Job JSON and GeoJSON files
- Advanced data analysis capabilities

## Detailed Command-Line Documentation

For in-depth options, examples, and troubleshooting for each standalone script see the dedicated READMEs inside the `docs/` folder:

- [Pole Comparison Tool](docs/pole_comparison_tool.md)
- [Cover Sheet Tool](docs/cover_sheet_tool.md)
- [MRR Tool](docs/mrr_tool.md)
- [SPIDA/Katapult QC Checker](docs/spidaqc.md)
- [How-To Guide CLI](docs/how_to_guide.md)

## Security

- All file processing is done server-side
- Uploaded files are automatically cleaned up after processing
- No data is stored permanently on the server
- Files are processed in isolated temporary directories

## Troubleshooting

### Common Issues

1. **File Upload Fails**
   - Check file size (must be under 50 MB)
   - Verify file format is supported
   - Check internet connection

2. **Processing Errors**
   - Verify file format and structure
   - Check for missing required columns/fields
   - Ensure data is properly formatted

3. **No Results**
   - Check if files contain expected data structure
   - Verify pole IDs match between files
   - Review file format requirements

4. **Performance Issues**
   - Use smaller files when possible
   - Close other browser tabs to free memory
   - Consider using desktop GUI for large files

### Getting Help

- Use the built-in "How To Guide" for detailed documentation
- Check file format specifications
- Ensure your data meets the requirements

## Development

### Project Structure
```
cps-energy-tools/
├── app.py                 # Main Flask application
├── templates/             # HTML templates
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   ├── pole_comparison.html
│   ├── cover_sheet.html
│   ├── mrr_tool.html
│   └── how_to_guide.html
├── static/               # Static files
│   ├── css/
│   │   └── style.css    # Main stylesheet
│   └── js/
│       └── pole_comparison.js
├── uploads/              # Temporary file uploads
├── pole_comparison_tool.py
├── cover_sheet_tool.py
├── how_to_guide.py
├── MattsMRR.py
└── requirements.txt
```

### Running in Development Mode
```bash
export FLASK_ENV=development  # Linux/Mac
set FLASK_ENV=development     # Windows
python app.py
```

### Running in Production
- Use a production WSGI server like Gunicorn
- Set up proper environment variables
- Configure reverse proxy (nginx/Apache)
- Enable HTTPS

## License

© 2024 CPS Energy Tools. All rights reserved.

## Original Tools

This web application is based on the existing Python command-line tools:
- `pole_comparison_tool.py`
- `cover_sheet_tool.py`
- `how_to_guide.py`
- `MattsMRR.py`

The web interface preserves all original functionality while providing a modern, user-friendly interface. 