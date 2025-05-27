# How-To Guide (how_to_guide.py)

This script is the **CLI documentation companion** for the CPS Energy Tools suite.  Run it to view interactive, paginated instructions without opening a browser.

---

## 1.  Sections Available

* Installation & Setup
* Pole Comparison Tool
* Cover Sheet Tool
* File Format Specifications

Each can be displayed individually using `--topic`, or all at once (default).

---

## 2.  Usage

```bash
# Show the entire guide
python how_to_guide.py

# Show only installation instructions
python how_to_guide.py --topic installation

# Show tool-specific help
python how_to_guide.py --topic pole-comparison
```

`--topic` accepts one of: `installation`, `pole-comparison`, `cover-sheet`, `file-formats`.

---

## 3.  Internals

* Plain-text printing – safe to pipe into `less`, `more`, or redirect to a file.
* Automatically adds the current year to the footer.
* Easy to extend: add a new `show_<topic>_guide()` method and include it in the parser choices.

---

## 4.  License

Refer to repository notice. 