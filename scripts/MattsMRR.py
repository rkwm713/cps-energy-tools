import types
# BEGIN PATCH: Safe tkinter import for headless environments
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except (ImportError, RuntimeError):
    # Create minimal stubs to satisfy attribute accesses when tkinter is unavailable (e.g., in headless servers)
    tk = types.ModuleType("tkinter_stub")
    def _stub(*args, **kwargs):
        return None
    class _StubWidget:
        def __init__(self, *args, **kwargs):
            pass
        def __getattr__(self, name):
            return _stub
        def grid(self, *args, **kwargs):
            pass
        def grid_remove(self, *args, **kwargs):
            pass
        def insert(self, *args, **kwargs):
            pass
        def delete(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            return ""
    tk.Tk = _StubWidget
    tk.Text = _StubWidget
    tk.END = "end"
    tk.W = "w"
    # ttk & other dialogs fall back to stub widgets/functions
    ttk = types.ModuleType("ttk_stub")
    ttk.Label = _StubWidget
    ttk.Entry = _StubWidget
    ttk.Button = _StubWidget
    messagebox = types.ModuleType("msgbox_stub")
    filedialog = types.ModuleType("filedialog_stub")
    filedialog.askopenfilename = _stub
    tk.StringVar = lambda *args, **kwargs: types.SimpleNamespace(get=lambda: "", set=lambda v: None)
# END PATCH
import pandas as pd
import json
import datetime
import os
from pathlib import Path

from cps_tools.core.mrr.excel_formatter_utils import (
    compare_scids,
    get_attachers_for_node,
    get_lowest_heights_for_connection,
    get_attachment_action,
    get_pole_structure,
    get_proposed_guy_value,
    get_work_type,
    get_responsible_party,
    calculate_bearing # Needed for process_data logic
)
from cps_tools.core.mrr.excel_writer import write_formatted_excel


class FileProcessorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Processor")
        self.geometry("500x350")
        self.downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")

        self.job_json_path = tk.StringVar()
        self.geojson_path = tk.StringVar()
        self.latest_output_path = None

        ttk.Label(self, text="Job JSON:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self, textvariable=self.job_json_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(self, text="Browse", command=lambda: self.browse_file("job")).grid(row=0, column=2)

        ttk.Label(self, text="GeoJSON:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self, textvariable=self.geojson_path, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(self, text="Browse", command=lambda: self.browse_file("geojson")).grid(row=1, column=2)

        ttk.Button(self, text="Process Files", command=self.process_files).grid(row=2, column=0, columnspan=3, pady=20)

        self.info_text = tk.Text(self, height=8, width=60)
        self.info_text.grid(row=3, column=0, columnspan=3, pady=10)

        self.open_file_button = ttk.Button(self, text="Open Output File", command=self.open_output_file)
        self.open_file_button.grid(row=4, column=0, columnspan=3, pady=10)
        self.open_file_button.grid_remove()

    def browse_file(self, file_type):
        filetypes = {
            "job": [("JSON files", "*.json")],
            "geojson": [("GeoJSON files", "*.json *.geojson")]
        }
        filename = filedialog.askopenfilename(initialdir=self.downloads_path, filetypes=filetypes[file_type])
        if filename:
            if file_type == "job":
                self.job_json_path.set(filename)
            elif file_type == "geojson":
                self.geojson_path.set(filename)

    def open_output_file(self):
        if self.latest_output_path:
            os.startfile(self.latest_output_path)

    def load_json(self, path):
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def process_files(self):
        self.info_text.delete(1.0, tk.END)
        try:
            # Validate job JSON path
            job_json_path = self.job_json_path.get()
            if not job_json_path:
                self.info_text.insert(tk.END, "Error: Please select a Job JSON file.\n")
                return
                
            if not os.path.exists(job_json_path):
                self.info_text.insert(tk.END, f"Error: Job JSON file not found: {job_json_path}\n")
                return

            self.job_data = self.load_json(job_json_path)  # Store as instance variable
            
            # Make GeoJSON loading optional
            geojson_data = None
            geojson_path = self.geojson_path.get()
            if geojson_path:
                if not os.path.exists(geojson_path):
                    self.info_text.insert(tk.END, f"Warning: GeoJSON file not found: {geojson_path}\n")
                    self.info_text.insert(tk.END, "Continuing without GeoJSON data...\n")
                else:
                    try:
                        geojson_data = self.load_json(geojson_path)
                        self.info_text.insert(tk.END, "GeoJSON file loaded successfully.\n")
                    except Exception as e:
                        self.info_text.insert(tk.END, f"Warning: Could not load GeoJSON file: {str(e)}\n")
                        self.info_text.insert(tk.END, "Continuing without GeoJSON data...\n")
            else:
                self.info_text.insert(tk.END, "No GeoJSON file selected. Processing without GeoJSON data...\n")

            self.info_text.insert(tk.END, "Job JSON file loaded successfully.\n")
            
            # Call the external process function
            output_path_from_processor, stats = process(
                job_json=Path(job_json_path),
                geojson=Path(geojson_path) if geojson_path else None,
                output=None # Let the processor handle output path generation
            )
            df_rows = stats.get("rows", 0)

            if df_rows == 0:
                self.info_text.insert(tk.END, "Warning: DataFrame is empty. No data to export.\n")
                return

            self.latest_output_path = output_path_from_processor
            self.open_file_button.grid()
            self.info_text.insert(tk.END, f"Successfully created output file: {self.latest_output_path}\n")
            self.info_text.insert(tk.END, f"DataFrame contains {df_rows} rows.\n")
        except Exception as e:
            self.info_text.insert(tk.END, f"Error processing files: {str(e)}\n")
            import traceback
            self.info_text.insert(tk.END, f"Traceback: {traceback.format_exc()}\n")


if __name__ == "__main__":
    app = FileProcessorGUI()
    app.mainloop()
