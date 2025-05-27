import json
from typing import Any, Dict, List, Tuple

# === Configuration Tables ===
# Crossarm mapping: (max_diameter_inch) -> crossarm type
CROSSARM_TABLE: List[Tuple[float, str]] = [
    (0.26, 'Standard'),
    (0.32, 'Standard'),
    (0.40, 'Standard'),
    (0.50, 'Heavy Duty'),
    (0.60, 'Heavy Duty'),
    (0.72, '8\" XHD'),
    (1.11, '8\" XHD'),
]

# TXDOT insulators requirements
TXDOT_INSULATORS = {
    'Communications':    {'Slack': "3\" Clevis Insulator", 'Full': "Communication D/E"},
    '90° Angle Com':     {'Slack': "Communication D/E",     'Full': "Communication D/E"},
    'Primary':           {'Slack': "24.9Kv Dead End Insulator", 'Full': "24.9Kv Dead End Insulator"},
    'Neutral (B)':       {'Slack': "3\" Clevis Insulator", 'Full': "Neutral D/E Clamp"},
}

# Guying requirements
GUYING_REQS = {
    'COM - Fiber':   {'Anchor': '8\" Single Helix 3/4\" Rod', 'Strand': '1/4\" EHS'},
    'COM - Telco':   {'Anchor': '8\" Single Helix 3/4\" Rod', 'Strand': '3/8\" EHS'},
    'Power - Single Phase': {'Anchor': '8\" Expanding', 'Strand': '3/8\" EHS'},
    'Power - Dual Phase':   {'Anchor': 'Check Guying Diagram (C)', 'Strand': '3/8\" EHS'},
    'Power - Three Phase':  {'Anchor': 'Check Guying Diagram (C)', 'Strand': '3/8\" EHS'},
}

class QCChecker:
    """Performs quality-control checks comparing SPIDAcalc and Katapult JSONs.

    Issues are grouped by the pole / structure id they relate to so the UI can
    display an expandable section per pole.  Any issue that cannot be
    attributed to a specific pole will be placed in the special "General"
    bucket.
    """

    GENERAL_KEY = "General"

    def __init__(self, spida: Dict[str, Any], kata: Dict[str, Any]):
        self.spida = spida if isinstance(spida, dict) else {}
        self.kata = kata if isinstance(kata, dict) else {}

        # issues grouped by pole id -> list[str]
        self.issues_by_pole: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def _add_issue(self, pole_id: Any, message: str):
        """Add an issue string under the specified pole id bucket."""
        key = str(pole_id) if pole_id else self.GENERAL_KEY
        self.issues_by_pole.setdefault(key, []).append(message)

    def _infer_pole_from_element(self, element: Dict[str, Any]) -> str:
        """Attempt to infer a pole / structure identifier from a JSON element.

        The SPIDA/Katapult schema isn't finalised, so we heuristically look for
        common keys that would reference a structure / location / pole.  If
        none are present, return an empty string so the caller can decide what
        bucket to place the message in.
        """
        if not isinstance(element, dict):
            return ""

        for k in ("structureId", "locationId", "poleId", "stationId", "pole_id", "structure_id"):
            if k in element and element[k]:
                return str(element[k])
        return ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def run_checks(self) -> Dict[str, List[str]]:
        # Core checks
        self.check_schema_version()
        self.check_missing_fields()
        self.check_crossarm_usage()
        self.check_owners_match()
        self.compare_wire_owners()
        self.check_fiber_counts()
        self.check_txdot_insulators()
        self.check_guying_requirements()
        # Additional checks
        self.check_duplicate_nodes()
        self.check_connection_lengths()

        return self.issues_by_pole

    def check_schema_version(self):
        # Ensure SPIDAcalc and Katapult versions match expected schema
        v = self.spida.get('version')
        if v != 11:
            self._add_issue(self.GENERAL_KEY, f"Unexpected SPIDAcalc schema version: {v}")

    def check_missing_fields(self):
        # Verify required top-level sections exist
        for key in ('wires', 'anchors', 'equipments'):
            if key not in self.spida:
                self._add_issue(self.GENERAL_KEY, f"Missing '{key}' section in SPIDA JSON.")

    def check_crossarm_usage(self):
        # Crossarm recommendation based on wire diameters
        for w in self.spida.get('wires', []):
            if not isinstance(w, dict):
                continue
            dia = w.get('diameter', {}).get('value', 0) * 39.37  # meter->inch
            rec = next((arm for max_dia, arm in CROSSARM_TABLE if dia <= max_dia), None)
            attached = w.get('recommendedCrossarmType')
            if rec and attached and rec != attached:
                pole = self._infer_pole_from_element(w)
                self._add_issue(pole, f"Wire '{w.get('description')}' (dia {dia:.3f}\") should use '{rec}' crossarm, found '{attached}'.")

    def check_owners_match(self):
        # Ensure SPIDA equipment owners match Katapult
        kp = {node.get('id'): node for node in self.kata.get('nodes', []) if isinstance(node, dict)}
        for eq in self.spida.get('equipments', []):
            if not isinstance(eq, dict):
                continue
            owner_spida = eq.get('type', {}).get('industry') if isinstance(eq.get('type'), dict) else None
            ext = eq.get('externalId')
            kat = next((n for n in self.kata.get('attachments', []) if isinstance(n, dict) and n.get('externalId') == ext), {})
            owner_kata = kat.get('owner', {}).get('industry') if isinstance(kat.get('owner'), dict) else None
            if owner_spida and owner_kata and owner_spida != owner_kata:
                pole = self._infer_pole_from_element(eq)
                self._add_issue(pole, f"Owner mismatch for attachment '{ext}': SPIDA '{owner_spida}', Katapult '{owner_kata}'")

    def compare_wire_owners(self):
        # Flag if wire usageGroup owner doesn't match SPIDA attachments
        for w in self.spida.get('wires', []):
            if not isinstance(w, dict):
                continue
            ug = w.get('usageGroups', [])
            wid = w.get('id')
            for att in self.spida.get('attachments', []):
                if not isinstance(att, dict):
                    continue
                if wid and wid in att.get('wireIds', []) and att.get('owner') not in ug:
                    pole = self._infer_pole_from_element(att)
                    self._add_issue(pole, f"Attachment '{att.get('id', 'unknown')}' has wire '{wid}' but owner mismatch.")

    def check_fiber_counts(self):
        # Ensure fiber counts are consistent between Katapult and SPIDA
        for w in self.spida.get('wires', []):
            if not isinstance(w, dict):
                continue
            if 'Fiber' in w.get('description', ''):
                cnt_spida = w.get('fiberCount')
                wid = w.get('id')
                kata_wire = next((kw for kw in self.kata.get('wires', []) if isinstance(kw, dict) and kw.get('id') == wid), {})
                cnt_kata = kata_wire.get('fiberCount')
                if cnt_spida != cnt_kata:
                    pole = self._infer_pole_from_element(w)
                    self._add_issue(pole, f"Fiber count mismatch for wire {wid}: SPIDA {cnt_spida}, Kata {cnt_kata}")

    def check_txdot_insulators(self):
        # San Antonio/TXDOT insulator requirements
        for att in self.spida.get('attachments', []):
            if not isinstance(att, dict):
                continue
            atype = att.get('attachmentType')
            tension = att.get('tensionGroup')  # 'Slack' or 'Full'
            req = TXDOT_INSULATORS.get(atype, {})
            found = att.get('insulatorType')
            want = req.get(tension)
            if want and found != want:
                pole = self._infer_pole_from_element(att)
                self._add_issue(pole, f"TXDOT: '{atype}' {tension} requires '{want}', found '{found}'.")

    def check_guying_requirements(self):
        # Check guy anchors and strands
        for g in self.spida.get('guys', []):
            if not isinstance(g, dict):
                continue
            gtype = g.get('guyType')
            req = GUYING_REQS.get(gtype)
            found_anchor = g.get('anchorType')
            found_strand = g.get('strandSize')
            if req and (found_anchor != req['Anchor'] or found_strand != req['Strand']):
                gid = g.get('id', 'unknown')
                pole = self._infer_pole_from_element(g)
                self._add_issue(pole, f"Guy '{gid}' {gtype} requires anchor '{req['Anchor']}' and strand '{req['Strand']}', found anchor '{found_anchor}', strand '{found_strand}'.")

    def check_duplicate_nodes(self):
        # Simple duplicate node ID check
        ids = [n.get('id') for n in self.spida.get('nodes', []) if isinstance(n, dict)]
        dups = set([x for x in ids if ids.count(x) > 1])
        for d in dups:
            self._add_issue(self.GENERAL_KEY, f"Duplicate node ID found: {d}")

    def check_connection_lengths(self):
        # Ensure connection length within reasonable limits
        connections = self.kata.get('connections', {})
        if isinstance(connections, dict):
            iterable = connections.values()
        elif isinstance(connections, list):
            iterable = connections
        else:
            iterable = []

        for conn in iterable:
            if not isinstance(conn, dict):
                continue
            sections = conn.get('sections', {})
            if isinstance(sections, dict):
                section_iter = sections.values()
            elif isinstance(sections, list):
                section_iter = sections
            else:
                section_iter = []

            # placeholder: iterate to ensure no type errors
            for sec in section_iter:
                if not isinstance(sec, dict):
                    continue
                _ = sec.get('multi_attributes', {}).get('field_completed')
        # TODO: Implement actual length check logic once schema confirmed


def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r') as f:
        return json.load(f)


def main(spida_path: str, kata_path: str):
    spida = load_json(spida_path)
    kata = load_json(kata_path)
    checker = QCChecker(spida, kata)
    issues = checker.run_checks()
    if issues:
        print("QC Issues Found:")
        for pole, issues in issues.items():
            print(f"Pole: {pole}")
            for issue in issues:
                print(f" - {issue}")
    else:
        print("No QC issues detected.")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run QC checks on SPIDAcalc & Katapult JSONs')
    parser.add_argument('spida_json', help='Path to SPIDAcalc JSON file')
    parser.add_argument('kata_json', help='Path to Katapult JSON file')
    args = parser.parse_args()
    main(args.spida_json, args.kata_json)
