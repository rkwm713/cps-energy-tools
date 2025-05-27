# SPIDA / Katapult QC Checker (spidaqc.py)

A lightweight command-line inspection tool that performs **quality-control** checks on two JSON exports:

1. **SPIDAcalc** design file
2. **Katapult (Photofirst)** JSON job file

It scans for schema mismatches, owner inconsistencies, cross-arm violations, TXDOT requirements, and more – returning all found issues grouped by pole for easy triage.

---

## 1.  Core Checks Implemented

| Category | Example Issue Description |
| -------- | ------------------------- |
| Schema | Unexpected SPIDAcalc schema version |
| Missing Sections | "Missing 'equipments' section in SPIDA JSON" |
| Cross-arm | Wire diameter 0.45" should use 8" XHD but found Standard |
| Owner | Owner mismatch for attachment *123* – SPIDA "Communications", Katapult "Power" |
| Wire Owner | Attachment has wire id but owner mismatch |
| Fiber Counts | Fiber count mismatch between files |
| TXDOT Insulators | Slack span must use "3" Clevis Insulator" |
| Guying | Wrong anchor / strand size for guy type |
| Duplicate Nodes | Duplicate node ID detected |
| Connection Lengths | Flagged when length outside expected range (placeholder) |

The checker is **extensible** – add new rules by creating methods that call `_add_issue()`.

---

## 2.  Running the Tool

```bash
python spidaqc.py spida.json katapult.json
```

Output example:

```
QC Issues Found:
Pole: 1-PL410620
 - Owner mismatch for attachment 'ATT-12': SPIDA "Communications", Katapult "Power"
 - Wire 'Fiber 144' (dia 0.50") should use '8" XHD' crossarm, found 'Standard'.
Pole: General
 - Unexpected SPIDAcalc schema version: 10
```

If **no** issues are found the script exits with a friendly message.

---

## 3.  Adding Checks

Each public `check_*` method is called by `run_checks()`.  Inside a check use:

```python
self._add_issue(pole_id, "message")
```

Pass an empty string or `QCChecker.GENERAL_KEY` to collect non-pole-specific issues under the *General* bucket.

---

## 4.  Integration

Import the class and use programmatically:

```python
from spidaqc import QCChecker, load_json

spida = load_json('s.json')
kat   = load_json('k.json')
issues = QCChecker(spida, kat).run_checks()
for pole, msgs in issues.items():
    ...
```

---

## 5.  License

Refer to repository notice. 