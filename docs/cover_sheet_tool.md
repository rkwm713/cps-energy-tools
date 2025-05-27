# Cover Sheet Tool

Generates a fully-formatted cover-sheet summary for a SPIDAcalc job – perfect for pasting into project documentation or submitting alongside design packages.

---

## 1.  What it Does

* 📝 Extracts **project meta-data** – job number, date, location, city, engineer.
* 🪧 Builds a **Pole Data Summary** table that lists Station ID, existing loading %, final loading %, and notes.
* 🗺️ If latitude/longitude are present it reverse-geocodes the first pole to obtain a human-readable address (OpenStreetMap / Nominatim).
* 🔢 Calculates a succinct *"N PLAs on M poles"* comment string by counting attachments across the entire file.
* 👉 Outputs the result as **console text** for quick copy-&-paste; can be redirected to file.

---

## 2.  Input

A standard SPIDAcalc JSON export.  The tool walks the structure `leads → locations → designs` and looks for:

* `label`, `date`, `engineer`, `clientData.generalLocation`, `address.city`  
  for project-level fields.
* `design.analysis[].results[]` where `analysisType == "STRESS"` and `unit == "PERCENT"`  
  to obtain existing & final loading.

The script is tolerant of missing keys and prints debug output when data can't be found.

---

## 3.  Quick Start

```bash
python cover_sheet_tool.py project.json > cover.txt
```

The generated text will look like:

```
==============================================================================================
POLE DATA SUMMARY
==============================================================================================
SCID  Station ID      Address                  Existing Loading %   Final Loading %     Notes
----------------------------------------------------------------------------------------------
1     410620          123 Main St, San Antonio  65.3%                92.1%             
2     410621                               ...
```

---

## 4.  Command-line Options

| Option | Required | Description |
| ------ | -------- | ----------- |
| `spida_file` | ✔ | Path to the SPIDAcalc JSON export |
| `--help` | – | Show built-in help |

> Tip   Redirect `stdout` to a file (`> cover_sheet.txt`) or pipe to the clipboard (`| clip` on Windows).

---

## 5.  Reverse-Geocoding & Rate Limits

The script queries the **Nominatim** API once (at most) – subject to its 1 request / sec policy.
A one-second `sleep()` is baked in to stay compliant.  If the request fails, the tool falls back to
"Address lookup failed" but continues processing.

---

## 6.  Troubleshooting

| Symptom | Fix |
| ------- | --- |
| *Missing project fields* | Ensure your SPIDAcalc export includes the relevant keys; check the debug output printed to the console. |
| *Address lookup failed* | Verify the pole has geographic coordinates; check internet connectivity; or try again later (Nominatim throttling). |
| *Loading columns show N/A* | The STRESS/PERCENT results were not found – confirm the designs contain analysis results. |

---

## 7.  Extending

The function `extract_cover_sheet_data()` is cleanly separated from the CLI – import it from other Python scripts to obtain a structured `dict` instead of formatted text.

---

## 8.  License

Refer to the repository-level license notice. 