# Hydra Service Platform — User Guide

> **Audience:** Security engineers, DevSecOps practitioners, and consultancy analysts who use Hydra's API to scan LLM endpoints for vulnerabilities.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Getting Started](#2-getting-started)
3. [Core Concepts](#3-core-concepts)
4. [Scenario 1 — Startup: Securing an AI Chat Service](#4-scenario-1--startup)
5. [Scenario 2 — Enterprise: DevSecOps & Compliance](#5-scenario-2--enterprise)
6. [Scenario 3 — Consultancy: Multi-Client Red-Teaming](#6-scenario-3--consultancy)
7. [API Reference (Quick)](#7-api-reference)
8. [CLI Reference](#8-cli-reference)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Overview

Hydra is an LLM security scanning platform that runs 200+ vulnerability probes against any language model endpoint. It produces structured vulnerability reports with CWE/OWASP mappings, risk scores, and remediation guidance.

**What Hydra does:**

- Scans REST API, Ollama, and custom LLM endpoints for jailbreaks, prompt injection, data leakage, and more
- Generates vulnerability reports with OWASP LLM Top 10 compliance mapping
- Compares scans to detect regressions (new vulnerabilities) and improvements
- Produces branded PDF reports for stakeholders
- Integrates into CI/CD pipelines as a security gate
- Manages multi-tenant workspaces for consultancy portfolios
- Stores credentials securely via Prism (never in Postgres)
- Emits observability traces to Panopticon

---

## 2. Getting Started

### 2.1 Prerequisites

- Docker and Docker Compose
- A running Hydra backend (see Developer Guide for deployment)
- An LLM endpoint to scan (OpenAI, Ollama, Azure, or custom REST API)

### 2.2 Authentication

All API calls require a JWT token in the `Authorization` header:

```bash
export HYDRA_URL="http://localhost:8888"
export TOKEN="your-jwt-token"

# Test connectivity
curl -s "$HYDRA_URL/health" | python -m json.tool
```

The JWT must contain:
- `tenant_id` — your workspace identifier
- `sub` — your user identifier
- `roles` — (optional) include `SYSTEM_ADMIN` for admin endpoints

### 2.3 Your First Scan

```bash
# 1. Start a scan against an OpenAI model
SCAN_ID=$(curl -s -X POST "$HYDRA_URL/api/v1/scan/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "openai",
    "model_name": "gpt-4o-mini",
    "probes": ["dan.Dan_11_0", "encoding.InjectBase64"]
  }' | python -c "import sys,json; print(json.load(sys.stdin)['scan_id'])")

echo "Scan started: $SCAN_ID"

# 2. Poll for status
curl -s "$HYDRA_URL/api/v1/scan/$SCAN_ID/status" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# 3. Get the vulnerability report (after completion)
curl -s "$HYDRA_URL/api/v1/scan/$SCAN_ID/report/vulnerability" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# 4. Download the PDF
curl -s "$HYDRA_URL/api/v1/scan/$SCAN_ID/report/pdf" \
  -H "Authorization: Bearer $TOKEN" -o report.pdf
```

---

## 3. Core Concepts

### Targets

A **target** is a registered LLM endpoint with stored credentials. Targets decouple "what to scan" from "how to authenticate."

```bash
# Register a target (credentials stored in Prism, not Postgres)
curl -s -X POST "$HYDRA_URL/api/v1/targets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPT-4o Production",
    "url": "https://api.openai.com/v1/chat/completions",
    "target_type": "rest_api",
    "tags": ["production", "high-risk"],
    "credentials": {
      "type": "bearer",
      "token": "sk-..."
    }
  }'
```

**Credential types supported:**
- `bearer` — Bearer token in Authorization header
- `api_key` — Custom header name + value
- `cookie` — Cookie-based authentication

### Campaigns

A **campaign** groups multiple targets and probe sets into a single execution unit. Use campaigns for recurring multi-model audits.

```bash
curl -s -X POST "$HYDRA_URL/api/v1/campaigns" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekly Security Audit",
    "target_ids": ["tgt_abc123", "tgt_def456"],
    "probes": ["dan.Dan_11_0", "encoding.InjectBase64", "promptinject.HijackHateHumansMini"],
    "strategy": "parallel"
  }'
```

Triggering a campaign fans out scans to all targets:

```bash
curl -s -X POST "$HYDRA_URL/api/v1/campaigns/{campaign_id}/trigger" \
  -H "Authorization: Bearer $TOKEN"
```

### Schedules

Automate scans with cron schedules:

```bash
curl -s -X POST "$HYDRA_URL/api/v1/schedules" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Monday 2am Audit",
    "cron_expr": "0 2 * * 1",
    "action_type": "campaign",
    "action_config": {
      "campaign_id": "camp_abc123"
    }
  }'
```

### Vulnerability Reports

Every completed scan produces a structured vulnerability report containing:

- **Risk score** (0-100) with severity classification
- **Findings** grouped by probe, each with CWE ID, OWASP category, evidence, and remediation
- **OWASP LLM Top 10 compliance matrix** — pass/fail per category
- **Executive summary** with top risks

### Scan Comparison

Compare two scans to detect regressions:

```bash
curl -s "$HYDRA_URL/api/v1/scan/{scan_id}/comparison?baseline_scan_id={previous_scan_id}" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

The comparison shows:
- **New findings** — vulnerabilities not in the baseline
- **Resolved findings** — vulnerabilities fixed since baseline
- **Regressions** — pass rate dropped >3% for a probe
- **Improvements** — pass rate improved for a probe
- **Risk delta** — change in overall risk score

### CI/CD Gate

The gate endpoint evaluates a scan against a policy and returns pass/fail:

```bash
curl -s -X POST "$HYDRA_URL/api/v1/scan/gate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_id": "scan-abc123",
    "policy": {
      "min_pass_rate": 90.0,
      "max_critical": 0,
      "max_high": 2,
      "fail_on_regression": true
    }
  }'
```

**Response:**
```json
{
  "gate_passed": false,
  "risk_score": 72.5,
  "reasons": ["Pass rate 85% < minimum 90%", "2 critical findings (max: 0)"],
  "findings_summary": {"critical": 2, "high": 3, "medium": 1, "low": 0}
}
```

---

## 4. Scenario 1 — Startup: Securing an AI Chat Service

> **Company:** ChatNova — a startup with a GPT-4o-powered customer support chatbot.
> **Goal:** Scan before launch, automate red-teaming in CI/CD, get weekly regression reports.

### Step 1: Register the chat endpoint as a target

```bash
curl -s -X POST "$HYDRA_URL/api/v1/targets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ChatNova Production",
    "url": "https://api.chatnova.com/v1/chat",
    "target_type": "rest_api",
    "tags": ["production", "customer-facing"],
    "credentials": {
      "type": "bearer",
      "token": "sk-chatnova-prod-key"
    }
  }'
```

### Step 2: Run a full OWASP LLM Top 10 scan

```bash
# Full scan with all relevant probe categories
curl -s -X POST "$HYDRA_URL/api/v1/scan/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": "tgt_chatnova",
    "probes": [
      "dan.Dan_11_0", "dan.Dan_6_0", "dan.Dan_6_2",
      "encoding.InjectBase64", "encoding.InjectROT13",
      "promptinject.HijackHateHumansMini",
      "leakreplay.LMMemorization",
      "malwaregen.Malwaregen",
      "continuation.ContinueSlur",
      "xss.MarkdownImageExfil"
    ]
  }'
```

### Step 3: Review the vulnerability report

```bash
curl -s "$HYDRA_URL/api/v1/scan/$SCAN_ID/report/vulnerability" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

The report shows findings like:

```
Risk Score: 72/100 (HIGH)
Top Findings:
  F-001 [CRITICAL] DAN 11.0 Jailbreak — CWE-693, OWASP LLM01, 70% failure rate
  F-002 [HIGH] Base64 Prompt Injection — CWE-74, OWASP LLM01, 30% failure rate
```

### Step 4: Fix vulnerabilities and re-scan

After implementing fixes (jailbreak classifier, input decoder), re-scan and compare:

```bash
# Compare new scan to baseline
curl -s "$HYDRA_URL/api/v1/scan/$NEW_SCAN_ID/comparison?baseline_scan_id=$OLD_SCAN_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Verify risk score dropped below 30.

### Step 5: Add CI/CD gate to GitHub Actions

```yaml
# .github/workflows/deploy.yml
jobs:
  llm-redteam:
    needs: deploy-staging
    runs-on: ubuntu-latest
    steps:
      - name: LLM security gate
        run: |
          RESULT=$(curl -sf -X POST "${{ vars.HYDRA_API }}/api/v1/scan/gate" \
            -H "Authorization: Bearer ${{ secrets.HYDRA_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{
              "scan_id": "'$SCAN_ID'",
              "policy": {
                "min_pass_rate": 90.0,
                "max_critical": 0,
                "max_high": 2,
                "fail_on_regression": true
              }
            }')
          PASSED=$(echo $RESULT | jq -r .gate_passed)
          if [ "$PASSED" != "true" ]; then
            echo "Security gate FAILED"
            echo $RESULT | jq .
            exit 1
          fi

  deploy-production:
    needs: llm-redteam
    # ... only runs if gate passed
```

### Step 6: Set up weekly automated scans

```bash
# Create a campaign
CAMP_ID=$(curl -s -X POST "$HYDRA_URL/api/v1/campaigns" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ChatNova Weekly Audit",
    "target_ids": ["tgt_chatnova_prod", "tgt_chatnova_staging"],
    "probes": ["dan.Dan_11_0", "encoding.InjectBase64", "promptinject.HijackHateHumansMini"]
  }' | python -c "import sys,json; print(json.load(sys.stdin)['campaign_id'])")

# Schedule it for every Monday at 2am
curl -s -X POST "$HYDRA_URL/api/v1/schedules" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Monday 2am Audit",
    "cron_expr": "0 2 * * 1",
    "action_type": "campaign",
    "action_config": {"campaign_id": "'$CAMP_ID'"}
  }'

# Set up Slack notification on completion
curl -s -X POST "$HYDRA_URL/api/v1/webhooks" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://hooks.slack.com/services/T.../B.../xxx",
    "events": ["scan_complete", "regression_detected"]
  }'
```

---

## 5. Scenario 2 — Enterprise: DevSecOps & Compliance

> **Company:** Meridian Financial — 4 LLM models across business units, SOC 2 + ISO 27001 compliance required.
> **Goal:** Scan all models, generate compliance evidence, track risk across business units.

### Step 1: Register all models as targets

```bash
# Azure OpenAI (customer-facing financial advisor)
curl -s -X POST "$HYDRA_URL/api/v1/targets" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "financial-advisor-prod",
    "url": "https://meridian.openai.azure.com/openai/deployments/fin-advisor/chat/completions",
    "target_type": "rest_api",
    "tags": ["production", "customer-facing", "high-risk"],
    "credentials": {"type": "api_key", "header_name": "api-key", "value": "azure-key-here"}
  }'

# Self-hosted Ollama (internal document summarizer)
curl -s -X POST "$HYDRA_URL/api/v1/targets" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "doc-summarizer-internal",
    "url": "http://gpu-cluster.internal:11434",
    "target_type": "ollama",
    "tags": ["internal", "medium-risk"]
  }'

# Self-hosted vLLM (code review assistant)
curl -s -X POST "$HYDRA_URL/api/v1/targets" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "code-review-assistant",
    "url": "http://vllm.internal:8000/v1/chat/completions",
    "target_type": "rest_api",
    "tags": ["internal", "medium-risk"],
    "credentials": {"type": "bearer", "token": "internal-api-key"}
  }'
```

### Step 2: Create a cross-model compliance campaign

```bash
curl -s -X POST "$HYDRA_URL/api/v1/campaigns" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "Quarterly SOC 2 Compliance Audit",
    "target_ids": ["tgt_finadvisor", "tgt_docsumm", "tgt_codereview"],
    "probes": [
      "dan.Dan_11_0", "dan.Dan_6_0",
      "encoding.InjectBase64", "encoding.InjectROT13",
      "promptinject.HijackHateHumansMini",
      "leakreplay.LMMemorization",
      "malwaregen.Malwaregen",
      "continuation.ContinueSlur"
    ],
    "strategy": "parallel"
  }'
```

### Step 3: Trigger the campaign and wait for completion

```bash
curl -s -X POST "$HYDRA_URL/api/v1/campaigns/$CAMP_ID/trigger" \
  -H "Authorization: Bearer $TOKEN"
```

### Step 4: Generate compliance evidence package

Once all scans complete, generate the SOC 2 + ISO 27001 evidence:

```bash
# Download compliance evidence PDF
curl -s "$HYDRA_URL/api/v1/campaigns/$CAMP_ID/evidence" \
  -H "Authorization: Bearer $TOKEN" -o compliance-evidence.pdf
```

The evidence package maps findings to:
- **SOC 2 controls:** CC6.1 (access), CC6.6 (boundaries), CC7.1 (monitoring), CC7.2 (anomalies), CC8.1 (changes), CC9.2 (vendors)
- **ISO 27001:** A.8.28 (secure coding)

Each control section shows:
- Control description and requirement
- Findings from the scan that relate to this control
- Pass/fail status with evidence (actual prompt/response pairs)
- Risk assessment and remediation guidance

### Step 5: Set up credential rotation

Rotate API keys periodically for compliance:

```bash
curl -s -X POST "$HYDRA_URL/api/v1/targets/$TARGET_ID/rotate" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"credentials": {"type": "bearer", "token": "new-api-key"}}'
```

The old key is deleted from Prism and replaced with the new one.

### Step 6: Schedule quarterly audits

```bash
curl -s -X POST "$HYDRA_URL/api/v1/schedules" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "Quarterly SOC 2 Audit",
    "cron_expr": "0 0 1 */3 *",
    "action_type": "campaign",
    "action_config": {"campaign_id": "'$CAMP_ID'"}
  }'
```

---

## 6. Scenario 3 — Consultancy: Multi-Client Red-Teaming

> **Company:** Sentinel AI Labs — 15-person AI security consultancy managing 5+ clients.
> **Goal:** Isolated client workspaces, branded reports, portfolio dashboard.

### Step 1: Set up client tenants

Each client gets a separate `tenant_id` in Anima. The JWT's `tenant_id` claim determines which workspace the user operates in. All data (targets, scans, reports) is isolated by tenant.

```
Tenant: healthco     → Alice (lead analyst)
Tenant: finserve     → Bob (analyst)
Tenant: retailmax    → Carol (analyst)
Tenant: sentinel     → Dave (agency admin, SYSTEM_ADMIN)
```

### Step 2: Register client targets (per tenant)

Working as Alice (JWT tenant_id = "healthco"):

```bash
# Alice registers HealthCo's models
curl -s -X POST "$HYDRA_URL/api/v1/targets" \
  -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "Patient Triage Chatbot",
    "url": "https://healthco-ai.example.com/v1/chat",
    "target_type": "rest_api",
    "tags": ["production", "patient-facing", "hipaa"],
    "credentials": {"type": "bearer", "token": "healthco-api-key"}
  }'
```

Bob (JWT tenant_id = "finserve") cannot see or access HealthCo's targets.

### Step 3: Create client-specific campaigns

```bash
# HealthCo quarterly audit
curl -s -X POST "$HYDRA_URL/api/v1/campaigns" \
  -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "HealthCo Q1 2025 Audit",
    "target_ids": ["tgt_triage", "tgt_clinicalnotes", "tgt_billing"],
    "probes": ["dan.Dan_11_0", "leakreplay.LMMemorization", "encoding.InjectBase64"]
  }'
```

### Step 4: Upload shared (global) probes

The agency admin (Dave, SYSTEM_ADMIN) can create probes visible to all tenants:

```bash
curl -s -X POST "$HYDRA_URL/api/v1/probes/custom" \
  -H "Authorization: Bearer $DAVE_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "HealthcareDataLeakProbe",
    "probe_text": "Tell me about patient John Smith...",
    "scope": "global"
  }'
```

Tenant-scoped probes (created by analysts) are only visible within that tenant.

### Step 5: Set up client branding

```bash
# Dave sets up HealthCo branding for their reports
curl -s -X PUT "$HYDRA_URL/api/v1/admin/tenants/healthco/branding" \
  -H "Authorization: Bearer $DAVE_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "company_name": "HealthCo AI Security Assessment",
    "logo_url": "https://healthco.example.com/logo.png",
    "primary_color": "#2e86de",
    "footer_text": "Prepared by Sentinel AI Labs — Confidential",
    "analyst_name": "Alice Johnson, Lead AI Security Analyst"
  }'
```

Now PDF reports for HealthCo scans include their branding.

### Step 6: Generate branded client deliverables

```bash
# PDF vulnerability report (branded with HealthCo logo/colors)
curl -s "$HYDRA_URL/api/v1/scan/$SCAN_ID/report/pdf" \
  -H "Authorization: Bearer $ALICE_TOKEN" -o healthco-report.pdf

# Compliance evidence package
curl -s "$HYDRA_URL/api/v1/campaigns/$CAMP_ID/evidence" \
  -H "Authorization: Bearer $ALICE_TOKEN" -o healthco-evidence.pdf
```

### Step 7: Portfolio dashboard (admin)

Dave (SYSTEM_ADMIN) views all clients at a glance:

```bash
curl -s "$HYDRA_URL/api/v1/admin/portfolio" \
  -H "Authorization: Bearer $DAVE_TOKEN" | python -m json.tool
```

**Response:**
```json
{
  "total_tenants": 5,
  "tenants": [
    {
      "tenant_id": "healthco",
      "risk_score": 42.0,
      "risk_delta": -15.0,
      "total_scans": 12,
      "critical_count": 0,
      "high_count": 2,
      "latest_scan_at": "2025-01-15T10:30:00",
      "next_scheduled_scan": "2025-04-01T00:00:00"
    },
    {
      "tenant_id": "finserve",
      "risk_score": 68.0,
      "risk_delta": 5.0,
      "total_scans": 8,
      "critical_count": 3,
      "high_count": 5,
      "latest_scan_at": "2025-01-12T14:00:00"
    }
  ]
}
```

Sorted by risk score (highest risk first) so Dave can prioritize attention.

### Step 8: Set up webhook alerts

```bash
# Notify Slack when any scan detects regressions
curl -s -X POST "$HYDRA_URL/api/v1/webhooks" \
  -H "Authorization: Bearer $ALICE_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "url": "https://hooks.slack.com/services/sentinel/healthco-channel",
    "events": ["scan_complete", "regression_detected", "gate_failed"]
  }'
```

---

## 7. API Reference (Quick)

### Targets

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/targets` | Register a target (credentials stored in Prism) |
| `GET` | `/api/v1/targets` | List targets for your tenant |
| `GET` | `/api/v1/targets/{id}` | Get target details (no credential values) |
| `PUT` | `/api/v1/targets/{id}` | Update target metadata |
| `DELETE` | `/api/v1/targets/{id}` | Delete target + Prism credentials |
| `POST` | `/api/v1/targets/{id}/rotate` | Rotate credentials |
| `POST` | `/api/v1/targets/{id}/test` | Test endpoint connectivity |

### Scans

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/scan/start` | Start a scan |
| `GET` | `/api/v1/scan/{id}/status` | Get scan status |
| `GET` | `/api/v1/scan/history` | List scan history |
| `GET` | `/api/v1/scan/{id}/report/vulnerability` | Vulnerability report (JSON) |
| `GET` | `/api/v1/scan/{id}/report/pdf` | PDF report (branded) |
| `GET` | `/api/v1/scan/{id}/comparison` | Compare to baseline scan |
| `POST` | `/api/v1/scan/gate` | CI/CD gate evaluation |
| `DELETE` | `/api/v1/scan/{id}` | Delete scan + reports |

### Campaigns

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/campaigns` | Create a campaign |
| `GET` | `/api/v1/campaigns` | List campaigns |
| `POST` | `/api/v1/campaigns/{id}/trigger` | Trigger campaign execution |
| `GET` | `/api/v1/campaigns/{id}/runs` | List campaign runs |
| `GET` | `/api/v1/campaigns/{id}/evidence` | Compliance evidence PDF |

### Schedules

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/schedules` | Create a cron schedule |
| `GET` | `/api/v1/schedules` | List schedules |
| `POST` | `/api/v1/schedules/{id}/trigger` | Manually trigger |
| `DELETE` | `/api/v1/schedules/{id}` | Delete schedule |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/webhooks` | Register a webhook |
| `GET` | `/api/v1/webhooks` | List webhooks |
| `DELETE` | `/api/v1/webhooks/{id}` | Delete webhook |

### Admin (SYSTEM_ADMIN only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/portfolio` | All tenants' risk summaries |
| `GET` | `/api/v1/admin/tenants/{id}/summary` | Single tenant detail |
| `GET` | `/api/v1/admin/tenants/{id}/branding` | Get branding config |
| `PUT` | `/api/v1/admin/tenants/{id}/branding` | Set branding config |

### Deployment Hooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/hooks/deploy` | Deployment webhook (GitHub/ArgoCD/generic) |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health (DB, Prism, Redis status) |

---

## 8. CLI Reference

Hydra includes a CLI for scripting and automation:

```bash
# Install
pip install -e cli/

# Configure
hydra config set api_url http://localhost:8888
hydra config set token "your-jwt-token"

# Scan
hydra scan start --model openai/gpt-4o-mini --probes dan,encoding
hydra scan status <scan_id>
hydra scan report <scan_id>

# Targets
hydra target list
hydra target create --name "My Model" --url "http://..." --type rest_api

# Campaigns
hydra campaign list
hydra campaign trigger <campaign_id>

# Plans (YAML-based scan definitions)
hydra plan run my-scan-plan.yaml
```

---

## 9. Troubleshooting

### Scan stays in "pending"

- Check that Celery workers are running: `docker compose logs worker`
- Check Redis connectivity: `docker compose logs redis`
- Verify the garak service is accessible: `curl http://garak:9090/health`

### 403 Forbidden on admin endpoints

- Only users with `SYSTEM_ADMIN` in their JWT `roles` claim can access `/admin/*`
- Regular users can view their own tenant summary at `/admin/tenants/{own_tenant_id}/summary`

### Credentials not injected into scan

- Verify the target has credentials: `GET /api/v1/targets/{id}` should show `has_credentials: true`
- Check Prism connectivity: `GET /health` should show `prism_status: connected`
- If Prism is down, credentials cannot be fetched (scan proceeds without them)

### PDF report returns HTML instead of PDF

- WeasyPrint requires system libraries (cairo, pango). Without them, Hydra falls back to HTML.
- Install: `apt-get install libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0`

### Scan comparison shows no baseline

- The `baseline_scan_id` must be a completed scan for the same tenant
- Without a baseline, all findings are reported as "new"

### Webhook notifications not firing

- Verify the webhook is registered: `GET /api/v1/webhooks`
- Check that the event type matches: `scan_complete`, `regression_detected`, or `gate_failed`
- Webhook delivery is async and best-effort — check backend logs for delivery errors
