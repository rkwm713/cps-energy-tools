# MRR Tool (MattsMRR.py)

Multi-Report Reader (MRR) processes **Job JSON** + **GeoJSON** files produced by Photofirst/Katapult and generates an Excel workbook summarising pole attachers, heights, back-span data, and movement summaries.  The script can be run in two modes:

1. Desktop **GUI** (Tkinter) – drag-and-drop friendly, ships with the web app as a separate window.
2. **CLI/Batch** – call the processing functions directly from your own Python scripts.

---

## 1.  Highlights

* 📑 **Comprehensive Excel output** – tables, colour formatting, formulas; ready for submission.
* 🖼️ **GUI conveniences** – file pickers, last-output quick-open button, inline status log.
* 📏 **Accurate height conversions** – raw inches → feet-inch string helper.
* 🧮 **Attachment analysis** – extracts existing & proposed heights, differentiates power vs communication, includes guying attachments below neutral.
* 🧭 **Back-span bearing** calculation and lowest height capture.

---

## 2.  File Inputs

| Argument | Type | Description |
| -------- | ---- | ----------- |
| `job_json` | `.json` | Katapult/Photofirst job export containing nodes, traces, photos, etc. |
| `geojson` | `.geojson` / `.json` | GeoJSON with spatial data for the same project |

Both files are required for full processing.

---

## 3.  Launching the GUI

```bash
python MattsMRR.py
```

1. Click **Browse** next to *Job JSON* and *GeoJSON* to select the files.
2. Press **Process Files** – the log window will indicate progress.
3. After completion the *Open Output File* button becomes active to launch Excel.

> The output is saved to your **Downloads** folder using the pattern `MRR_YYYYMMDD_HHMMSS.xlsx`.

---

## 4.  Running Headless / Importing

The heavy-lifting happens in `FileProcessorGUI.process_files()`.  If you want to automate MRR generation:

```python
from MattsMRR import FileProcessorGUI

gui = FileProcessorGUI()
# set paths programmatically
gui.job_json_path.set('job.json')
gui.geojson_path.set('map.geojson')
# run
gui.process_files()
print('Created:', gui.latest_output_path)
```

Tkinter dependencies are stubbed when no display is available so the module still imports on servers.

---

## 5.  Excel Sheet Overview

| Sheet | Description |
| ----- | ----------- |
| `Summary` | High-level movement summaries (all attachers & CPS-only) |
| `Pole Data` | Main per-pole and per-span attachment listings |
| `Reference` | Lowest comms & CPS heights per connection |

---

## 6.  Troubleshooting

* GUI window doesn't show – Ensure a local Python with Tkinter is installed; on headless machines use CLI import mode.
* `ValueError: could not convert string to float` – Check that measurement fields in Job JSON are numeric.
* Attachment ordering looks off – The script sorts by raw height (inches) descending; verify the input data.

---

## 7.  License

See repository root notice. 