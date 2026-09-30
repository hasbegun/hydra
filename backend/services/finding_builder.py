"""
Finding builder — transforms raw JSONL attempt entries into structured
``Finding`` objects enriched with CWE/OWASP metadata from
``probe_knowledge``.

Responsibilities:
  1. Group raw attempt entries by probe classname
  2. Count pass/fail per probe
  3. Collect evidence (prompt/response pairs), limited to max_evidence
  4. Enrich each finding with metadata from ``probe_knowledge``
  5. Classify severity using ``risk_scorer.classify_finding_severity``
"""
import logging
from typing import Optional

from models.report_schemas import Finding, FindingEvidence
from services.probe_knowledge import get_probe_metadata
from services.risk_scorer import classify_finding_severity

logger = logging.getLogger(__name__)

# Maximum evidence pairs to keep per finding
MAX_EVIDENCE_PER_FINDING = 5


def _extract_prompt(entry: dict) -> str:
    """Extract prompt text from a JSONL attempt entry."""
    prompt = entry.get("prompt", {})
    if isinstance(prompt, str):
        return prompt
    turns = prompt.get("turns", [])
    if turns:
        content = turns[0].get("content", {})
        if isinstance(content, dict):
            return content.get("text", "")
        return str(content)
    return ""


def _extract_output(entry: dict) -> str:
    """Extract the first output text from a JSONL attempt entry."""
    outputs = entry.get("outputs", [])
    if outputs:
        first = outputs[0]
        if isinstance(first, dict):
            return first.get("text", "")
        return str(first)
    return ""


def build_findings(
    entries: list,
    max_evidence: int = MAX_EVIDENCE_PER_FINDING,
) -> list[Finding]:
    """Build Finding objects from raw JSONL entries.

    Parameters
    ----------
    entries : list[dict]
        Raw JSONL entries from a garak report. Only ``entry_type == "attempt"``
        entries are processed.
    max_evidence : int
        Maximum number of evidence pairs per finding.

    Returns
    -------
    list[Finding]
        Findings sorted by severity (critical first), then by failure rate
        descending.
    """
    # Phase 1: group by probe
    probe_data: dict[str, dict] = {}

    for entry in entries:
        if entry.get("entry_type") != "attempt":
            continue

        probe = entry.get("probe_classname", "unknown")
        if probe not in probe_data:
            probe_data[probe] = {
                "passed": 0,
                "failed": 0,
                "evidence": [],
            }

        status = entry.get("status")
        if status == 2:
            probe_data[probe]["passed"] += 1
        elif status == 1:
            probe_data[probe]["failed"] += 1
            # Collect failed evidence (limited)
            if len(probe_data[probe]["evidence"]) < max_evidence:
                probe_data[probe]["evidence"].append(
                    FindingEvidence(
                        prompt=_extract_prompt(entry),
                        response=_extract_output(entry),
                        result="fail",
                    )
                )

    # Phase 2: enrich and build Finding objects
    from services.gate_evaluator import SEVERITY_WEIGHTS

    findings: list[Finding] = []

    for probe_name, data in probe_data.items():
        total = data["passed"] + data["failed"]
        if total == 0:
            continue

        failure_rate = data["failed"] / total
        metadata = get_probe_metadata(probe_name)

        # Use knowledge-base severity as a hint, but escalate on high failure rate
        kb_severity = metadata.get("severity")
        severity = classify_finding_severity(probe_name, failure_rate, override=kb_severity)

        finding = Finding(
            probe=probe_name,
            category=metadata.get("category", probe_name.split(".")[0]),
            severity=severity,
            description=metadata.get("description", ""),
            risk_explanation=metadata.get("risk_explanation", ""),
            mitigation=metadata.get("mitigation", ""),
            cwe_ids=metadata.get("cwe_ids", []),
            owasp_llm=metadata.get("owasp_llm", []),
            total_attempts=total,
            failed_attempts=data["failed"],
            failure_rate=round(failure_rate, 4),
            evidence=data["evidence"],
        )
        findings.append(finding)

    # Sort: critical first, then by failure rate desc
    severity_order = {s: i for i, s in enumerate(["critical", "high", "medium", "low", "info"])}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 99), -f.failure_rate))

    return findings
