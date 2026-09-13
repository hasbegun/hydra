"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class ScanStatus(str, Enum):
    """Scan execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GeneratorType(str, Enum):
    """Supported generator types"""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    REPLICATE = "replicate"
    COHERE = "cohere"
    ANTHROPIC = "anthropic"
    LITELLM = "litellm"
    NIM = "nim"
    GROQ = "groq"
    MISTRAL = "mistral"
    AZURE = "azure"
    BEDROCK = "bedrock"
    REST = "rest"


class ScanConfigRequest(BaseModel):
    """Request model for starting a scan"""
    target_type: str = Field(..., description="Generator type (e.g., 'openai')")
    target_name: str = Field(..., description="Model name (e.g., 'gpt-3.5-turbo')")
    probes: List[str] = Field(default=["all"], description="List of probe names or 'all'")
    detectors: Optional[List[str]] = Field(default=None, description="List of detector names (optional)")
    buffs: Optional[List[str]] = Field(default=None, description="List of buffs to apply (optional)")

    # Run parameters
    generations: int = Field(default=5, ge=1, le=500, description="Number of generations per prompt")
    eval_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Evaluation threshold")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")

    # System parameters
    parallel_requests: Optional[int] = Field(default=None, ge=1, description="Parallel requests count")
    parallel_attempts: Optional[int] = Field(default=None, ge=1, description="Parallel attempts count")

    # Options
    generator_options: Optional[Dict[str, Any]] = Field(default=None, description="Generator-specific options")
    probe_options: Optional[Dict[str, Any]] = Field(default=None, description="Probe-specific options")

    # Reporting
    report_prefix: Optional[str] = Field(default=None, description="Prefix for report files")

    # Filtering
    probe_tags: Optional[str] = Field(
        default=None,
        description="Filter probes by tag prefix (e.g., 'owasp:llm01')"
    )

    # System prompt
    system_prompt: Optional[str] = Field(
        default=None,
        description="Custom system prompt for the LLM"
    )

    # Extended detectors
    extended_detectors: bool = Field(
        default=False,
        description="Run all detectors instead of primary only"
    )

    # Deprefix
    deprefix: bool = Field(
        default=False,
        description="Remove prompt from generator output before analysis"
    )

    # Verbose
    verbose: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Verbosity level (0=default, 1=-v, 2=-vv, 3=-vvv)"
    )

    # Skip unknown plugins
    skip_unknown: bool = Field(
        default=False,
        description="Skip unknown plugins instead of failing"
    )

    # Buffs include original prompt
    buffs_include_original_prompt: bool = Field(
        default=False,
        description="Include original prompt alongside buffed versions"
    )

    # Output directory
    output_dir: Optional[str] = Field(
        default=None,
        description="Custom output directory for scan results"
    )

    # No report
    no_report: bool = Field(
        default=False,
        description="Skip report generation"
    )

    # Continue on error
    continue_on_error: bool = Field(
        default=False,
        description="Continue scan even if some probes fail"
    )

    # REST target fields (for scanning HTTP/REST LLM endpoints)
    rest_endpoint: Optional[str] = Field(
        default=None,
        description="REST API endpoint URL for the target LLM service"
    )
    rest_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="HTTP headers for REST target requests (e.g., Authorization)"
    )
    rest_body_template: Optional[str] = Field(
        default=None,
        description="JSON body template for REST target; $INPUT is replaced with the attack prompt"
    )
    rest_response_json_field: Optional[str] = Field(
        default=None,
        description="JSON path to extract the LLM response from the REST API response"
    )

    # Exclude probes
    exclude_probes: Optional[str] = Field(
        default=None,
        description="Comma-separated list of probes to exclude"
    )

    # Exclude detectors
    exclude_detectors: Optional[str] = Field(
        default=None,
        description="Comma-separated list of detectors to exclude"
    )

    # Timeout per probe
    timeout_per_probe: Optional[int] = Field(
        default=None,
        ge=1,
        le=3600,
        description="Timeout in seconds for each probe (1-3600)"
    )

    # Config file
    config_file: Optional[str] = Field(
        default=None,
        description="Path to a YAML/JSON config file for garak"
    )

    # Hit rate
    hit_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Stop scanning a probe after this hit rate is reached (0.0-1.0)"
    )

    # Report threshold
    report_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Only report results above this threshold (0.0-1.0)"
    )

    # Collect timing
    collect_timing: bool = Field(
        default=False,
        description="Collect timing metrics for each probe"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_type": "openai",
                "target_name": "gpt-3.5-turbo",
                "probes": ["dan", "encoding"],
                "generations": 10,
                "eval_threshold": 0.5,
                "generator_options": {
                    "temperature": 0.7,
                    "api_key": "sk-..."
                },
                "probe_tags": "owasp:llm01"
            }
        }


class ScanResponse(BaseModel):
    """Response model for scan initiation"""
    scan_id: str = Field(..., description="Unique scan identifier")
    status: ScanStatus = Field(..., description="Current scan status")
    message: str = Field(..., description="Status message")
    created_at: str = Field(..., description="Scan creation timestamp")


class ScanStatusResponse(BaseModel):
    """Response model for scan status query"""
    scan_id: str
    status: ScanStatus
    progress: float = Field(ge=0.0, le=100.0, description="Progress percentage")
    current_probe: Optional[str] = Field(default=None, description="Currently executing probe")
    completed_probes: int = Field(default=0, description="Number of completed probes")
    total_probes: int = Field(default=0, description="Total number of probes")
    passed: int = Field(default=0, description="Number of passed tests")
    failed: int = Field(default=0, description="Number of failed tests")
    elapsed_time: Optional[float] = Field(default=None, description="Elapsed time in seconds")
    estimated_remaining: Optional[float] = Field(default=None, description="Estimated remaining time")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


class ScanSortField(str, Enum):
    """Fields that can be used for sorting scan history"""
    STARTED_AT = "started_at"
    COMPLETED_AT = "completed_at"
    STATUS = "status"
    TARGET_NAME = "target_name"
    PASS_RATE = "pass_rate"


class SortOrder(str, Enum):
    """Sort order"""
    ASC = "asc"
    DESC = "desc"


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")


class ScanHistoryItem(BaseModel):
    """Single scan item in history"""
    scan_id: str
    status: str
    target_type: Optional[str] = None
    target_name: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    passed: int = 0
    failed: int = 0
    total_tests: int = 0
    progress: float = 0.0
    html_report_path: Optional[str] = None
    jsonl_report_path: Optional[str] = None


class ScanHistoryResponse(BaseModel):
    """Paginated response for scan history"""
    scans: List[ScanHistoryItem]
    pagination: PaginationMeta
    total_count: int = Field(..., description="Total number of scans (for backward compatibility)")


class PluginInfo(BaseModel):
    """Information about a plugin (probe, detector, generator, buff)"""
    name: str = Field(..., description="Plugin name")
    full_name: str = Field(..., description="Fully qualified plugin name")
    description: Optional[str] = Field(default=None, description="Plugin description")
    active: bool = Field(default=True, description="Whether plugin is active by default")
    tags: Optional[List[str]] = Field(default=None, description="Plugin tags")
    primary_detector: Optional[str] = Field(default=None, description="Primary detector (for probes)")
    goal: Optional[str] = Field(default=None, description="Plugin goal/purpose")


class PluginListResponse(BaseModel):
    """Response model for plugin listing"""
    plugins: List[PluginInfo]
    total_count: int


class ConfigPreset(BaseModel):
    """Configuration preset"""
    name: str = Field(..., description="Preset name")
    description: Optional[str] = Field(default=None, description="Preset description")
    config: Dict[str, Any] = Field(..., description="Configuration dictionary")


class ConfigTemplateSave(BaseModel):
    """Request to save a user config template"""
    name: str = Field(..., min_length=1, max_length=100, description="Template name (unique identifier)")
    description: Optional[str] = Field(default=None, max_length=500, description="Template description")
    config: Dict[str, Any] = Field(..., description="Scan configuration dictionary")


class ConfigTemplate(BaseModel):
    """Stored user config template"""
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(default=None, description="Template description")
    config: Dict[str, Any] = Field(..., description="Scan configuration dictionary")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")


class ConfigTemplateListResponse(BaseModel):
    """Response for listing user templates"""
    templates: List[ConfigTemplate] = Field(default_factory=list, description="User config templates")
    total_count: int = Field(default=0, description="Total number of templates")


class SystemInfoResponse(BaseModel):
    """System information response"""
    garak_version: str
    python_version: str
    backend_version: str
    garak_installed: bool
    available_generators: List[str]


class ScanResult(BaseModel):
    """Detailed scan result"""
    scan_id: str
    status: ScanStatus
    config: Optional[ScanConfigRequest] = Field(default=None, description="Scan configuration (may not be available for historical scans)")
    results: Dict[str, Any]
    report_path: Optional[str] = Field(default=None)
    created_at: Optional[str] = Field(default=None, description="When the scan was created (may not be available for historical scans)")
    started_at: Optional[str] = Field(default=None, description="When the scan actually started")
    completed_at: Optional[str] = Field(default=None)
    duration: Optional[float] = Field(default=None, description="Scan duration in seconds")
    summary: Optional[Dict[str, Any]] = Field(default=None, description="Results summary")
    digest: Optional[Dict[str, Any]] = Field(default=None, description="Per-probe evaluation digest from garak report")
    html_report_path: Optional[str] = Field(default=None, description="Path to HTML report file")
    jsonl_report_path: Optional[str] = Field(default=None, description="Path to JSONL report file")


# Custom Probe Models
class CustomProbeTemplate(str, Enum):
    """Available probe templates"""
    MINIMAL = "minimal"
    BASIC = "basic"
    ADVANCED = "advanced"


class CustomProbeCreateRequest(BaseModel):
    """Request to create a custom probe"""
    name: str = Field(..., description="Probe class name (must be valid Python identifier)")
    code: str = Field(..., description="Python code for the probe")
    description: Optional[str] = Field(default=None, description="Probe description")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "MyCustomProbe",
                "code": "import garak.probes.base\n\nclass MyCustomProbe(garak.probes.base.Probe):\n    \"\"\"My custom probe\"\"\"\n    prompts = ['Test prompt 1', 'Test prompt 2']",
                "description": "A custom probe for testing"
            }
        }


class CustomProbeValidateRequest(BaseModel):
    """Request to validate probe code"""
    code: str = Field(..., description="Python code to validate")


class ValidationError(BaseModel):
    """Validation error details"""
    line: Optional[int] = Field(default=None, description="Line number where error occurred")
    column: Optional[int] = Field(default=None, description="Column number where error occurred")
    message: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error (syntax, import, structure, etc.)")


class CustomProbeValidationResponse(BaseModel):
    """Response for probe validation"""
    valid: bool = Field(..., description="Whether the probe code is valid")
    errors: List[ValidationError] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    probe_info: Optional[Dict[str, Any]] = Field(default=None, description="Extracted probe information if valid")


class CustomProbe(BaseModel):
    """Custom probe metadata"""
    name: str = Field(..., description="Probe class name")
    file_path: str = Field(..., description="Path to probe file")
    description: Optional[str] = Field(default=None, description="Probe description")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    goal: Optional[str] = Field(default=None, description="Probe goal")
    tags: Optional[List[str]] = Field(default=None, description="Probe tags")
    primary_detector: Optional[str] = Field(default=None, description="Primary detector")


class CustomProbeListResponse(BaseModel):
    """Response for listing custom probes"""
    probes: List[CustomProbe] = Field(..., description="List of custom probes")
    total_count: int = Field(..., description="Total number of custom probes")


class CustomProbeGetResponse(BaseModel):
    """Response for getting a specific custom probe"""
    probe: CustomProbe = Field(..., description="Probe metadata")
    code: str = Field(..., description="Probe source code")


# ============================================================================
# Workflow Models
# ============================================================================

class WorkflowNodeType(str, Enum):
    """Types of nodes in workflow graph"""
    PROBE = "probe"
    GENERATOR = "generator"
    DETECTOR = "detector"
    LLM_RESPONSE = "llm_response"
    VULNERABILITY = "vulnerability"


class WorkflowEdgeType(str, Enum):
    """Types of edges/connections in workflow"""
    PROMPT = "prompt"
    RESPONSE = "response"
    DETECTION = "detection"
    CHAIN = "chain"


class WorkflowNode(BaseModel):
    """A node in the workflow graph"""
    node_id: str = Field(..., description="Unique node identifier")
    node_type: WorkflowNodeType = Field(..., description="Type of node")
    name: str = Field(..., description="Node name")
    description: Optional[str] = Field(default=None, description="Node description")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata (timing, tokens, etc.)")
    timestamp: float = Field(..., description="Unix timestamp when node was created")


class WorkflowEdge(BaseModel):
    """An edge/connection in the workflow graph"""
    edge_id: str = Field(..., description="Unique edge identifier")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    edge_type: WorkflowEdgeType = Field(..., description="Type of edge")
    content_preview: str = Field(default="", description="Preview of content (first 100 chars)")
    full_content: str = Field(default="", description="Full content of interaction")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class VulnerabilityFinding(BaseModel):
    """Details about a vulnerability found during scan"""
    vulnerability_type: str = Field(..., description="Type of vulnerability")
    severity: str = Field(default="medium", description="Severity level (low, medium, high, critical)")
    probe_name: str = Field(..., description="Probe that found the vulnerability")
    node_path: List[str] = Field(default_factory=list, description="Path through graph to vulnerability")
    evidence: str = Field(..., description="Evidence of vulnerability")


class WorkflowTrace(BaseModel):
    """A single trace/execution path in the workflow"""
    trace_id: str = Field(..., description="Unique trace identifier")
    scan_id: str = Field(..., description="Parent scan ID")
    probe_name: str = Field(..., description="Probe name for this trace")
    nodes: List[WorkflowNode] = Field(default_factory=list, description="Nodes in this trace")
    edges: List[WorkflowEdge] = Field(default_factory=list, description="Edges in this trace")
    vulnerability_findings: List[VulnerabilityFinding] = Field(
        default_factory=list,
        description="Vulnerabilities found in this trace"
    )
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Trace statistics")


class WorkflowGraph(BaseModel):
    """Complete workflow graph for a scan"""
    scan_id: str = Field(..., description="Scan identifier")
    nodes: List[WorkflowNode] = Field(default_factory=list, description="All nodes in the graph")
    edges: List[WorkflowEdge] = Field(default_factory=list, description="All edges in the graph")
    traces: List[WorkflowTrace] = Field(default_factory=list, description="Individual execution traces")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Overall statistics")
    layout_hints: Dict[str, Any] = Field(default_factory=dict, description="Hints for frontend graph layout")

    class Config:
        json_schema_extra = {
            "example": {
                "scan_id": "scan_12345",
                "nodes": [
                    {
                        "node_id": "probe_1",
                        "node_type": "probe",
                        "name": "dan.Dan_11_0",
                        "description": "DAN jailbreak probe",
                        "metadata": {"probe_type": "jailbreak"},
                        "timestamp": 1705660800.0
                    }
                ],
                "edges": [],
                "traces": [],
                "statistics": {
                    "total_interactions": 10,
                    "vulnerabilities_found": 2
                },
                "layout_hints": {}
            }
        }


class WorkflowTimelineEvent(BaseModel):
    """A single event in the workflow timeline"""
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of event")
    timestamp: float = Field(..., description="Unix timestamp")
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(default=None, description="Event description")
    node_id: Optional[str] = Field(default=None, description="Associated node ID")
    prompt: Optional[str] = Field(default=None, description="Prompt content if applicable")
    response: Optional[str] = Field(default=None, description="Response content if applicable")
    duration_ms: Optional[float] = Field(default=None, description="Event duration in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class WorkflowExportRequest(BaseModel):
    """Request to export workflow"""
    format: str = Field(..., description="Export format (json, mermaid, dot, svg, html)")

    class Config:
        json_schema_extra = {
            "example": {
                "format": "json"
            }
        }


class WorkflowExportResponse(BaseModel):
    """Response for workflow export"""
    format: str = Field(..., description="Export format used")
    data: Optional[str] = Field(default=None, description="Exported data (for text formats)")
    file_path: Optional[str] = Field(default=None, description="Path to exported file (for binary formats)")
    download_url: Optional[str] = Field(default=None, description="URL to download the exported file")


# ============================================================================
# Probe Details Models
# ============================================================================

# ============================================================================
# Scan Statistics Models
# ============================================================================

class DailyTrendPoint(BaseModel):
    """A single day's scan statistics."""
    date: str = Field(..., description="ISO date (YYYY-MM-DD)")
    scan_count: int = Field(default=0, description="Number of scans on this day")
    avg_pass_rate: float = Field(default=0.0, description="Average pass rate (0-100)")
    total_passed: int = Field(default=0, description="Total passed tests")
    total_failed: int = Field(default=0, description="Total failed tests")


class ProbeFailureStat(BaseModel):
    """Aggregated failure statistics for a probe category."""
    probe_category: str = Field(..., description="Probe category name")
    failure_count: int = Field(default=0, description="Total failures across all scans")
    total_count: int = Field(default=0, description="Total tests across all scans")
    failure_rate: float = Field(default=0.0, description="Failure rate (0-100)")


class TargetStat(BaseModel):
    """Aggregated statistics for a scan target."""
    target_type: str = Field(..., description="Generator type")
    target_name: str = Field(..., description="Model name")
    scan_count: int = Field(default=0, description="Number of scans for this target")
    avg_pass_rate: float = Field(default=0.0, description="Average pass rate (0-100)")
    last_scanned: Optional[str] = Field(default=None, description="Most recent scan timestamp")


class ScanStatisticsResponse(BaseModel):
    """Aggregate scan statistics."""
    # Scan counts
    total_scans: int = Field(default=0, description="Total number of scans")
    completed_scans: int = Field(default=0, description="Completed scans")
    failed_scans: int = Field(default=0, description="Failed scans")
    cancelled_scans: int = Field(default=0, description="Cancelled scans")
    running_scans: int = Field(default=0, description="Currently running scans")

    # Test aggregates
    total_tests: int = Field(default=0, description="Total tests across all scans")
    total_passed: int = Field(default=0, description="Total passed tests")
    total_failed: int = Field(default=0, description="Total failed tests")
    overall_pass_rate: float = Field(default=0.0, description="Overall pass rate (0-100)")

    # Pass rate distribution
    avg_pass_rate: float = Field(default=0.0, description="Average pass rate across completed scans")
    min_pass_rate: Optional[float] = Field(default=None, description="Worst scan pass rate")
    max_pass_rate: Optional[float] = Field(default=None, description="Best scan pass rate")

    # Trends
    daily_trends: List[DailyTrendPoint] = Field(default_factory=list, description="Daily trend data (last 30 days)")

    # Top failures
    top_failing_probes: List[ProbeFailureStat] = Field(default_factory=list, description="Most frequently failing probe categories (top 10)")

    # Target breakdown
    target_breakdown: List[TargetStat] = Field(default_factory=list, description="Per-target statistics")


# ============================================================================
# Probe Details Models
# ============================================================================

class ProbeSecurityMetadata(BaseModel):
    """Security metadata for a probe category"""
    category: str = Field(..., description="Human-readable category name")
    severity: str = Field(..., description="Severity level (critical, high, medium, low, info)")
    description: str = Field(..., description="What this probe tests")
    risk_explanation: str = Field(..., description="Why failures matter")
    mitigation: str = Field(..., description="How to defend against this")
    cwe_ids: List[str] = Field(default_factory=list, description="CWE references")
    owasp_llm: List[str] = Field(default_factory=list, description="OWASP LLM Top 10 references")


class ProbeResult(BaseModel):
    """Per-probe summary in probe details list"""
    probe_classname: str = Field(..., description="Fully qualified probe class name")
    category: str = Field(..., description="Probe category (first part of classname)")
    passed: int = Field(default=0, description="Number of passed tests")
    failed: int = Field(default=0, description="Number of failed tests")
    total: int = Field(default=0, description="Total number of tests")
    pass_rate: float = Field(default=0.0, description="Pass rate percentage (0-100)")
    goal: Optional[str] = Field(default=None, description="Probe goal text")
    security: ProbeSecurityMetadata = Field(..., description="Security metadata")


class ProbeDetailsResponse(BaseModel):
    """Response for probe details endpoint"""
    scan_id: str = Field(..., description="Scan identifier")
    total_probes: int = Field(..., description="Total number of probes (before pagination)")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    probes: List[ProbeResult] = Field(default_factory=list, description="Probe results")


class AttemptDetail(BaseModel):
    """Individual test attempt detail"""
    uuid: str = Field(default="", description="Attempt UUID")
    seq: Optional[int] = Field(default=None, description="Sequence number")
    status: str = Field(..., description="Attempt status (passed, failed, unknown)")
    prompt_text: str = Field(default="", description="Prompt text sent to the model")
    output_text: str = Field(default="", description="First model output")
    all_outputs: List[str] = Field(default_factory=list, description="All model outputs")
    triggers: Optional[List[str]] = Field(default=None, description="Trigger patterns matched")
    detector_results: Dict[str, Any] = Field(default_factory=dict, description="Detector results")
    goal: Optional[str] = Field(default=None, description="Goal for this attempt")


class ProbeAttemptsResponse(BaseModel):
    """Response for probe attempts endpoint"""
    scan_id: str = Field(..., description="Scan identifier")
    probe_classname: str = Field(..., description="Probe class name")
    security: ProbeSecurityMetadata = Field(..., description="Security metadata for this probe")
    total_attempts: int = Field(..., description="Total number of attempts")
    total_passed: int = Field(default=0, description="Total passed attempts across all pages")
    total_failed: int = Field(default=0, description="Total failed attempts across all pages")
    filtered_total: int = Field(default=0, description="Total attempts matching current status filter")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    attempts: List[AttemptDetail] = Field(default_factory=list, description="Attempt details")
