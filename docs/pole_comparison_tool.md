# Pole Comparison Tool

A standalone command-line utility for validating that pole data exported from Katapult and SPIDAcalc are in agreement.  The tool is also embedded in the CPS Energy Tools web application, but it can be executed directly from the shell for batch workflows or CI pipelines.

---

## 1.  Features

* ⚖️ **Side-by-Side Comparison** – Compares every pole that appears in both systems: specification, existing loading %, and final loading %.
* 🔎 **Intelligent Matching** – Normalises pole identifiers and uses fallback heuristics (numeric extraction, SCID/DLOC pairing) to find matches even when the two exports use different naming conventions.
* 🚩 **Issue Detection** – Flags  
  * missing poles  
  * duplicate entries  
  * pole-spec mismatches (height / class / species)  
  * loading discrepancies over a configurable threshold (default 5 %).
* 📊 **CSV Export** – Optionally dumps the full comparison table or *issues-only* subset to a CSV file that can be opened in Excel.

---

## 2.  Supported Formats

| Source | Supported File Types |
| ------ | -------------------- |
| Katapult | `.xlsx` / `.xls` Excel workbook or a Job JSON export |
| SPIDAcalc | `.json` project export |

See *File format specifics* in the main repository README if you need the exact column / field names.

---

## 3.  Installation

```bash
# Clone repository (or copy the single file if you prefer)
$ git clone https://github.com/<your-org>/cps-energy-tools.git
$ cd cps-energy-tools

# Install Python dependencies
$ pip install -r requirements.txt
```

Python ≥ 3.7 is required.

---

## 4.  Usage

### 4.1 Basic command

```bash
python pole_comparison_tool.py katapult.xlsx spida.json
```

### 4.2 Options

```
--threshold FLOAT        Maximum allowed % difference before a pole is flagged (default 5.0)
--export FILE.csv        Export the entire comparison table to CSV
--export-issues-only     When used with --export, only rows that contain an issue are written
--help                   Show built-in help
```

### 4.3 Examples

1. Compare two files and print summary to the console (no export):

    ```bash
    python pole_comparison_tool.py KATAPULT.xlsx SPIDA.json
    ```

2. Compare with a stricter 2 % tolerance and export issues:

    ```bash
    python pole_comparison_tool.py KATAPULT.xlsx SPIDA.json \
        --threshold 2 --export issues.csv --export-issues-only
    ```

3. Feed the output straight into Excel (*Windows*):

    ```powershell
    python pole_comparison_tool.py K.xlsx S.json --export result.csv ; start result.csv
    ```

---

## 5.  Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | Completed with **no** issues detected |
| 1 | Completed but **issues were found** |
| 2 | Fatal error while reading files or parsing options |

---

## 6.  Implementation Notes

* Uses `pandas` for robust Excel parsing and `json` std-lib for SPIDAcalc files.
* The `PoleComparisonTool` class can be imported into other Python programs; `main()` is only a thin CLI wrapper.
* Extensive logging (`print`) is left in place intentionally – redirect `stdout` if you only care about the CSV.

---

## 7.  Troubleshooting

| Symptom | Possible Cause & Fix |
| ------- | -------------------- |
| "0 poles processed" | Column names in the Katapult spreadsheet don't match – see *ALLOWED_NODE_TYPES* and *field option lists* in the code.
| Poles reported *missing* in one file | Check that the pole IDs are spelled the same; consider the `extract_numeric_id` strategy mentioned above.
| Incorrect % numbers | The tool auto-detects 0-1 vs 0-100 formats but can be fooled by text – confirm the numeric columns in Excel.

---

## 8.  License

See root `LICENSE` / repository notice. 