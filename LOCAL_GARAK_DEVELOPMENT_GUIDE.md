# Local Garak Development Guide

This guide explains how to work with the local copy of garak in the Hydra project, make modifications, and implement enhanced reporting features.

## Table of Contents

1. [Setup](#setup)
2. [Project Structure](#project-structure)
3. [Development Workflow](#development-workflow)
4. [Implementing Enhanced Reporting](#implementing-enhanced-reporting)
5. [Testing Your Changes](#testing-your-changes)
6. [Troubleshooting](#troubleshooting)

---

## Setup

### Prerequisites

- Python 3.10 or higher
- pip
- Virtual environment (recommended)

### Initial Setup

1. **Navigate to the backend directory**:

```bash
cd /path/to/garak/hydra/backend
```

2. **Create and activate a virtual environment** (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies including local garak**:

```bash
pip install -r requirements.txt
```

This will install garak in **editable mode** from `./garak`, which means:
- Any changes you make to `./garak/garak/` will be immediately reflected
- No need to reinstall after making changes
- You can import garak normally: `import garak`

4. **Verify installation**:

```bash
python -c "import garak; print(garak.__version__)"
```

You should see the garak version (e.g., `0.13.3.pre1`).

---

## Project Structure

```
hydra/
├── backend/
│   ├── garak/                      # Local copy of garak (editable install)
│   │   ├── garak/                  # Main garak package
│   │   │   ├── __init__.py
│   │   │   ├── attempt.py          # ⭐ Core data model for test attempts
│   │   │   ├── probes/             # ⭐ Vulnerability test probes
│   │   │   │   ├── base.py         # Base probe class
│   │   │   │   ├── dan.py          # Jailbreak probes
│   │   │   │   ├── promptinject.py # Prompt injection probes
│   │   │   │   └── ...
│   │   │   ├── detectors/          # Result detectors
│   │   │   ├── analyze/            # ⭐ Report generation
│   │   │   │   ├── report_digest.py   # HTML report generator
│   │   │   │   ├── templates/         # Jinja2 templates
│   │   │   │   └── ...
│   │   │   └── report.py           # Report class
│   │   ├── pyproject.toml          # Garak package configuration
│   │   └── README.md
│   ├── api/                        # Hydra API routes
│   ├── services/
│   │   └── garak_wrapper.py        # ⭐ Garak CLI wrapper
│   ├── requirements.txt            # ⭐ Now includes -e ./garak
│   └── main.py
└── frontend/                       # Flutter frontend

⭐ = Key files for implementing enhancements
```

---

## Development Workflow

### Making Changes to Garak

Since garak is installed in editable mode (`-e ./garak`), you can modify files directly:

1. **Edit a garak file**:

```bash
# Example: Modify the Attempt class
vim hydra/backend/garak/garak/attempt.py
```

2. **Changes are immediately active** - no reinstall needed!

3. **Test your changes**:

```bash
# Run garak from command line
cd hydra/backend
python -m garak --help

# Or import in Python
python
>>> import garak
>>> from garak.attempt import Attempt
>>> # Your code here
```

### Using Local Garak in Hydra Backend

The Hydra backend (`garak_wrapper.py`) runs garak as a subprocess. With the local installation, it will use your modified version.

**Option 1: Continue using subprocess (current approach)**

The wrapper will automatically find and use the local garak:

```python
# In garak_wrapper.py
garak_path = shutil.which("garak")  # Finds the editable install
```

**Option 2: Import garak directly (for deeper integration)**

For more control (e.g., to capture mitigation data directly), you can import garak as a Python module:

```python
# Example: Direct import approach
import garak
from garak import _config
from garak.probes import dan
from garak.attempt import Attempt

# Initialize config
_config.load_config()

# Load a probe
probe = dan.DAN_Jailbreak()

# Generate attempts
attempts = probe.probe(generator)

# Access detailed information
for attempt in attempts:
    print(attempt.vulnerability_explanation)
    print(attempt.mitigation_recommendations)
```

---

## Implementing Enhanced Reporting

Follow these steps to add detailed scan information and mitigation recommendations to garak reports.

### Step 1: Enhance the Attempt Data Model

**File**: `hydra/backend/garak/garak/attempt.py`

Add new fields to the `Attempt` class:

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Attempt:
    # ... existing fields ...

    # NEW FIELDS - Add these
    vulnerability_explanation: Optional[str] = None
    """Human-readable explanation of why this attempt represents a vulnerability"""

    mitigation_recommendations: List[str] = field(default_factory=list)
    """List of actionable mitigation steps"""

    severity: Optional[str] = None  # "critical", "high", "medium", "low", "info"
    """Severity rating"""

    cwe_ids: List[str] = field(default_factory=list)
    """Common Weakness Enumeration IDs"""

    owasp_categories: List[str] = field(default_factory=list)
    """OWASP LLM Top 10 categories"""

    attack_technique: Optional[str] = None
    """Name of the attack technique"""

    reproduction_steps: List[str] = field(default_factory=list)
    """Step-by-step reproduction instructions"""

    timestamp: Optional[str] = None
    """ISO 8601 timestamp"""

    references: List[dict] = field(default_factory=list)
    """External references"""
```

Update the `as_dict()` method to include new fields:

```python
def as_dict(self) -> dict:
    """Converts the attempt to a dictionary."""
    # ... existing code ...

    result = {
        "entry_type": "attempt",
        "uuid": str(self.uuid),
        # ... existing fields ...

        # NEW FIELDS
        "vulnerability_explanation": self.vulnerability_explanation,
        "mitigation_recommendations": self.mitigation_recommendations,
        "severity": self.severity,
        "cwe_ids": self.cwe_ids,
        "owasp_categories": self.owasp_categories,
        "attack_technique": self.attack_technique,
        "reproduction_steps": self.reproduction_steps,
        "timestamp": self.timestamp,
        "references": self.references,
    }

    return result
```

### Step 2: Add Metadata to Probe Base Class

**File**: `hydra/backend/garak/garak/probes/base.py`

```python
class Probe:
    # ... existing fields ...

    # NEW CLASS ATTRIBUTES
    vulnerability_type: str = "Unknown"
    mitigation_guidance: List[str] = []
    severity_default: str = "medium"
    cwe_mappings: List[str] = []
    owasp_mappings: List[str] = []
    references: List[dict] = []

    def _attempt_prestore_hook(self, attempt, seq):
        """
        Hook called before storing an attempt.
        Override in subclasses to add vulnerability metadata.
        """
        pass
```

### Step 3: Enhance Specific Probes

**Example**: `hydra/backend/garak/garak/probes/dan.py`

```python
from datetime import datetime
from garak.attempt import ATTEMPT_COMPLETE

# Shared metadata for DAN probes
DAN_MITIGATION_GUIDANCE = [
    "Implement robust input validation to detect jailbreak patterns",
    "Add a second-pass safety filter on model outputs (e.g., Llama Guard)",
    "Use constitutional AI techniques to strengthen refusals",
    "Reinforce safety guidelines in system prompts",
    "Monitor and log repeated jailbreak attempts",
]

DAN_REFERENCES = [
    {
        "type": "paper",
        "title": "Jailbroken: How Does LLM Safety Training Fail?",
        "url": "https://arxiv.org/abs/2307.02483"
    },
    {
        "type": "guide",
        "title": "OWASP LLM01: Prompt Injection",
        "url": "https://owasp.org/www-project-top-10-for-large-language-model-applications/"
    }
]

class DAN_Jailbreak(Probe):
    # ... existing code ...

    # NEW: Add metadata
    vulnerability_type = "Alignment Bypass via Jailbreak"
    severity_default = "high"
    cwe_mappings = ["CWE-862"]  # Missing Authorization
    owasp_mappings = ["LLM01"]  # Prompt Injection
    mitigation_guidance = DAN_MITIGATION_GUIDANCE
    references = DAN_REFERENCES

    def _attempt_prestore_hook(self, attempt, seq):
        """Add vulnerability metadata to failed attempts"""
        from datetime import datetime

        # Always add timestamp
        attempt.timestamp = datetime.now().isoformat()

        # Check if attempt completed
        if attempt.status == ATTEMPT_COMPLETE:
            # Check if any detector failed (score > 0 means detection = failure)
            failed = any(
                any(score > 0 for score in scores)
                for scores in attempt.detector_results.values()
            )

            if failed:
                # Populate vulnerability metadata
                attempt.vulnerability_explanation = (
                    f"The model failed to resist the '{self.name}' jailbreak prompt. "
                    "This indicates the model's safety training can be bypassed, allowing "
                    "malicious users to elicit harmful or unethical content."
                )
                attempt.mitigation_recommendations = self.mitigation_guidance
                attempt.severity = self.severity_default
                attempt.cwe_ids = self.cwe_mappings
                attempt.owasp_categories = self.owasp_mappings
                attempt.attack_technique = f"Jailbreak ({self.name})"
                attempt.references = self.references

                # Generate reproduction steps
                prompt_preview = attempt.prompt.last_message().text[:200]
                if len(attempt.prompt.last_message().text) > 200:
                    prompt_preview += "..."

                attempt.reproduction_steps = [
                    f"1. Send this prompt to the model: \"{prompt_preview}\"",
                    "2. Examine the response for harmful or policy-violating content",
                    "3. If the model provides harmful content, it's vulnerable",
                    f"4. Severity: {self.severity_default} - jailbreaks undermine all safety measures"
                ]
```

### Step 4: Create Developer Report Generator

**File**: `hydra/backend/garak/garak/analyze/report_developer.py` (NEW FILE)

```python
#!/usr/bin/env python3
"""
Generate developer-friendly markdown reports from garak JSONL output.

Usage:
    python -m garak.analyze.report_developer <report.jsonl>
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def generate_developer_report(jsonl_path: str, output_path: str = None):
    """
    Generate a markdown report with detailed vulnerability information.

    Args:
        jsonl_path: Path to garak JSONL report file
        output_path: Path for output markdown file (default: same name with .md)
    """
    if output_path is None:
        output_path = str(Path(jsonl_path).with_suffix('.developer.md'))

    # Parse JSONL
    attempts = []
    config = {}
    init = {}

    with open(jsonl_path, 'r') as f:
        for line in f:
            record = json.loads(line.strip())
            if record['entry_type'] == 'attempt':
                attempts.append(record)
            elif record['entry_type'] == 'config':
                config = record
            elif record['entry_type'] == 'init':
                init = record

    # Group by severity
    by_severity = defaultdict(list)
    for attempt in attempts:
        # Only include failed attempts with vulnerability data
        if attempt.get('vulnerability_explanation'):
            severity = attempt.get('severity', 'info')
            by_severity[severity].append(attempt)

    # Generate markdown
    md = []
    md.append("# LLM Vulnerability Scan Report\n")
    md.append(f"**Model**: {config.get('plugins.target_name', 'Unknown')} ({config.get('plugins.target_type', 'Unknown')})\n")
    md.append(f"**Scan Date**: {init.get('start_time', 'Unknown')}\n")
    md.append(f"**Garak Version**: {init.get('garak_version', 'Unknown')}\n")
    md.append(f"**Run ID**: {init.get('run', 'Unknown')}\n")
    md.append("\n---\n\n")

    # Executive summary
    total_critical = len(by_severity['critical'])
    total_high = len(by_severity['high'])
    total_medium = len(by_severity['medium'])
    total_low = len(by_severity['low'])
    total_issues = total_critical + total_high + total_medium + total_low

    md.append("## Executive Summary\n\n")
    md.append(f"- **Total Vulnerabilities Found**: {total_issues}\n")
    md.append(f"- **Critical**: {total_critical}\n")
    md.append(f"- **High**: {total_high}\n")
    md.append(f"- **Medium**: {total_medium}\n")
    md.append(f"- **Low**: {total_low}\n")
    md.append("\n---\n\n")

    # Vulnerabilities by severity
    md.append("## Vulnerabilities Found\n\n")

    severity_emoji = {
        'critical': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }

    for severity in ['critical', 'high', 'medium', 'low']:
        if not by_severity[severity]:
            continue

        for i, attempt in enumerate(by_severity[severity], 1):
            emoji = severity_emoji.get(severity, '⚪')
            md.append(f"### {emoji} {severity.upper()}: {attempt.get('probe_classname', 'Unknown')}\n\n")

            md.append(f"**Severity**: {severity.title()}\n")

            if attempt.get('owasp_categories'):
                md.append(f"**OWASP Categories**: {', '.join(attempt['owasp_categories'])}\n")

            if attempt.get('cwe_ids'):
                md.append(f"**CWE IDs**: {', '.join(attempt['cwe_ids'])}\n")

            md.append(f"\n**Description**:\n{attempt.get('vulnerability_explanation', 'No description available.')}\n\n")

            # Attack details
            md.append("**Attack Prompt**:\n```\n")
            prompt_text = attempt.get('prompt', {}).get('turns', [{}])[0].get('content', {}).get('text', 'N/A')
            md.append(f"{prompt_text}\n")
            md.append("```\n\n")

            # Model response (if available)
            outputs = attempt.get('outputs', [])
            if outputs and outputs[0]:
                md.append("**Model Response**:\n```\n")
                md.append(f"{outputs[0].get('text', 'N/A')[:500]}\n")
                md.append("```\n\n")

            # Reproduction steps
            if attempt.get('reproduction_steps'):
                md.append("**How to Reproduce**:\n")
                for step in attempt['reproduction_steps']:
                    md.append(f"{step}\n")
                md.append("\n")

            # Mitigation recommendations
            if attempt.get('mitigation_recommendations'):
                md.append("**Mitigation Recommendations**:\n")
                for j, rec in enumerate(attempt['mitigation_recommendations'], 1):
                    md.append(f"{j}. {rec}\n")
                md.append("\n")

            # References
            if attempt.get('references'):
                md.append("**References**:\n")
                for ref in attempt['references']:
                    md.append(f"- [{ref.get('title', 'Link')}]({ref.get('url', '#')})\n")
                md.append("\n")

            md.append("---\n\n")

    # Reproduction commands
    md.append("## Reproduction Commands\n\n")
    md.append("To reproduce this scan exactly:\n\n")
    md.append("```bash\n")
    md.append(f"garak --target_type {config.get('plugins.target_type', 'unknown')} \\\n")
    md.append(f"      --target_name {config.get('plugins.target_name', 'unknown')} \\\n")
    if config.get('plugins.probe_spec'):
        md.append(f"      --probes {config.get('plugins.probe_spec')} \\\n")
    md.append(f"      --detectors auto\n")
    md.append("```\n\n")

    # Write to file
    with open(output_path, 'w') as f:
        f.write(''.join(md))

    print(f"Developer report written to: {output_path}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python -m garak.analyze.report_developer <report.jsonl>")
        sys.exit(1)

    generate_developer_report(sys.argv[1])
```

### Step 5: Update Hydra Backend to Parse New Fields

**File**: `hydra/backend/services/garak_wrapper.py`

Add a method to extract vulnerability information:

```python
def get_vulnerabilities(self, scan_id: str) -> List[Dict[str, Any]]:
    """
    Get detailed vulnerability information from a scan.

    Args:
        scan_id: Scan identifier

    Returns:
        List of vulnerabilities with mitigation recommendations
    """
    scan_info = self.get_scan_status(scan_id)
    if not scan_info:
        return []

    jsonl_path = scan_info.get('jsonl_report_path')
    if not jsonl_path or not Path(jsonl_path).exists():
        return []

    vulnerabilities = []

    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                record = json.loads(line.strip())

                # Only include attempts with vulnerability data
                if (record.get('entry_type') == 'attempt' and
                    record.get('vulnerability_explanation')):

                    vuln = {
                        'uuid': record.get('uuid'),
                        'probe': record.get('probe_classname'),
                        'severity': record.get('severity', 'info'),
                        'explanation': record.get('vulnerability_explanation'),
                        'mitigations': record.get('mitigation_recommendations', []),
                        'cwe_ids': record.get('cwe_ids', []),
                        'owasp_categories': record.get('owasp_categories', []),
                        'attack_technique': record.get('attack_technique'),
                        'reproduction_steps': record.get('reproduction_steps', []),
                        'references': record.get('references', []),
                        'prompt': record.get('prompt'),
                        'outputs': record.get('outputs'),
                        'timestamp': record.get('timestamp'),
                    }

                    vulnerabilities.append(vuln)

    except Exception as e:
        logger.error(f"Error reading vulnerabilities from {jsonl_path}: {e}")

    # Sort by severity
    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    vulnerabilities.sort(key=lambda x: severity_order.get(x['severity'], 5))

    return vulnerabilities
```

### Step 6: Add API Endpoint

**File**: `hydra/backend/api/routes/scan.py`

```python
@router.get("/{scan_id}/vulnerabilities", response_model=List[Dict[str, Any]])
async def get_scan_vulnerabilities(scan_id: str):
    """
    Get detailed vulnerability information for a scan.

    Returns list of vulnerabilities with mitigation recommendations.
    """
    vulnerabilities = garak_wrapper.get_vulnerabilities(scan_id)

    if not vulnerabilities:
        raise HTTPException(
            status_code=404,
            detail=f"No vulnerabilities found for scan {scan_id}"
        )

    return vulnerabilities
```

---

## Testing Your Changes

### Test 1: Verify Attempt Enhancements

```python
# test_attempt.py
from garak.attempt import Attempt

# Create an attempt with new fields
attempt = Attempt()
attempt.vulnerability_explanation = "Test explanation"
attempt.mitigation_recommendations = ["Fix 1", "Fix 2"]
attempt.severity = "high"

# Verify serialization
data = attempt.as_dict()
assert 'vulnerability_explanation' in data
assert data['severity'] == 'high'
print("✅ Attempt enhancements work!")
```

### Test 2: Run a Scan with Enhanced Probe

```bash
# Run garak with an enhanced probe
cd hydra/backend
python -m garak \
    --target_type ollama \
    --target_name gemma3 \
    --probes dan.DAN_Jailbreak \
    --generations 5
```

Check the JSONL report for new fields:

```bash
# View the most recent report
cat ~/.local/share/garak/garak_runs/garak.*.report.jsonl | jq 'select(.entry_type=="attempt") | {vulnerability_explanation, mitigation_recommendations, severity}'
```

### Test 3: Generate Developer Report

```bash
# Generate markdown report
python -m garak.analyze.report_developer ~/.local/share/garak/garak_runs/garak.<scan-id>.report.jsonl

# View the report
cat ~/.local/share/garak/garak_runs/garak.<scan-id>.developer.md
```

### Test 4: Test Hydra API Integration

```bash
# Start Hydra backend
cd hydra/backend
python main.py

# In another terminal, run a scan via API
curl -X POST http://localhost:8888/api/v1/scan/start \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "ollama",
    "target_name": "gemma3",
    "probes": ["dan.DAN_Jailbreak"],
    "detectors": ["auto"],
    "generations": 5
  }'

# Get scan ID from response, then fetch vulnerabilities
curl http://localhost:8888/api/v1/scan/<scan-id>/vulnerabilities
```

---

## Troubleshooting

### Issue: Changes to garak not taking effect

**Solution**: Verify editable install:

```bash
pip show garak | grep Location
# Should point to: /path/to/hydra/backend/garak

# If not, reinstall in editable mode:
pip uninstall garak
pip install -e ./garak
```

### Issue: Import errors after adding new fields

**Solution**: Restart Python interpreter / backend server to reload modules.

### Issue: JSONL reports don't have new fields

**Solution**: Ensure `_attempt_prestore_hook` is being called. Add debug logging:

```python
def _attempt_prestore_hook(self, attempt, seq):
    print(f"DEBUG: prestore hook called for {attempt.uuid}")
    # ... rest of code
```

### Issue: Hydra backend can't find garak

**Solution**: Set `GARAK_PATH` in `.env`:

```bash
# hydra/backend/.env
GARAK_PATH=/path/to/hydra/backend/venv/bin/garak
```

---

## Quick Reference Commands

```bash
# Install dependencies with local garak
pip install -r requirements.txt

# Run garak from command line
python -m garak --help

# Generate developer report
python -m garak.analyze.report_developer <report.jsonl>

# Start Hydra backend
cd hydra/backend
python main.py

# Run tests
pytest hydra/tests/

# Check garak location
pip show garak

# Reinstall garak in editable mode
pip install -e ./garak --force-reinstall
```

---

## Next Steps

1. **Implement Phase 1**: Start with DAN probes as a prototype
2. **Test thoroughly**: Run scans and verify enhanced reports
3. **Gather feedback**: Share with team and iterate
4. **Expand coverage**: Apply enhancements to all probe categories
5. **Update frontend**: Display mitigation recommendations in UI
6. **Document best practices**: Create probe development guide

---

**For full proposal details**, see [GARAK_ENHANCEMENT_PROPOSAL.md](./GARAK_ENHANCEMENT_PROPOSAL.md)
