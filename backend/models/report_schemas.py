"""
Vulnerability report Pydantic schemas.

Defines the structured report format returned by
``GET /scan/{id}/report/vulnerability``.

Three top-level sections:
  1. ``executive_summary`` — risk score, finding counts, top risks
  2. ``findings`` — grouped by severity with CWE/OWASP/evidence/remediation
  3. ``compliance`` — OWASP LLM Top 10 matrix
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FindingEvidence(BaseModel):
    """A single prompt/response pair demonstrating the finding."""
    prompt: str = ""
    response: str = ""
    result: str = "fail"  # "pass" or "fail"


class Finding(BaseModel):
    """A single vulnerability finding (grouped by probe)."""
    probe: str
    category: str = ""
    severity: str = "info"  # critical, high, medium, low, info
    description: str = ""
    risk_explanation: str = ""
    mitigation: str = ""
    cwe_ids: list[str] = Field(default_factory=list)
    owasp_llm: list[str] = Field(default_factory=list)
    total_attempts: int = 0
    failed_attempts: int = 0
    failure_rate: float = 0.0
    evidence: list[FindingEvidence] = Field(default_factory=list)


class OWASPCategory(BaseModel):
    """One entry in the OWASP LLM Top 10 compliance matrix."""
    id: str           # e.g. "LLM01"
    name: str         # e.g. "Prompt Injection"
    status: str       # "pass", "fail", "not_tested"
    probes_tested: list[str] = Field(default_factory=list)
    finding_count: int = 0


class ExecutiveSummary(BaseModel):
    """High-level overview for executives."""
    risk_score: float = 0.0
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    top_risks: list[str] = Field(default_factory=list)


class VulnerabilityReport(BaseModel):
    """Full structured vulnerability report."""
    scan_id: str
    tenant_id: str = "default"
    target_name: str = ""
    target_type: str = ""
    generated_at: str = ""
    executive_summary: ExecutiveSummary = Field(default_factory=ExecutiveSummary)
    findings: list[Finding] = Field(default_factory=list)
    compliance: list[OWASPCategory] = Field(default_factory=list)
