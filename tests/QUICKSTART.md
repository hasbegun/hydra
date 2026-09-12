# Quick Start Guide

Get started testing in under 5 minutes.

## Prerequisites Check

```bash
# 1. Check Hydra backend is running
curl http://localhost:8888/health
# Expected: {"status":"healthy"}

# 2. Check Open WebUI is accessible
curl -H "Authorization: Bearer sk-15bdf48030cd4a7e8ee6d98e2ff3faa2" \
  http://localhost:3030/api/v1/models
# Expected: List of available models
```

## Install Dependencies

```bash
cd /Users/innox/projects/garak/hydra/tests
pip install -r requirements.txt
```

## Run Your First Test

### Option 1: Interactive Menu (Recommended)

```bash
python run_all_tests.py
```

Then select:
- `[1]` for Prompt Injection tests (~30-45 min)
- `[2]` for Jailbreak & DAN tests (~45-60 min)
- `[A]` to run all sections (~2-4 hours)

### Option 2: Single Section

```bash
# Run just prompt injection tests
python section_1_prompt_injection.py
```

### Option 3: Quick Test

Edit `section_1_prompt_injection.py` and change generations to 3:

```python
tester.run_test(
    test_name="1.1 System Prompt Extraction",
    probes=[...],
    generations=3  # Changed from 10 to 3
)
```

Then run:
```bash
python section_1_prompt_injection.py
```

## What You'll See

```
======================================================================
  PROMPT INJECTION
======================================================================
Description:  Tests for system prompt extraction and instruction override
Severity:     CRITICAL
Time:         30-45 min
======================================================================

▶ Running: 1.1 System Prompt Extraction
  Probes: promptinject.HijackKillHumans, promptinject.HijackHatesHumans
  Generations: 10
------------------------------------------------------------
  Scan ID: a1b2c3d4
  Status: PENDING
  Monitoring scan progress...

  Progress: 45.2% | Probe: promptinject.HijackKillHumans | ✓ 8 | ✗ 2
```

## View Results

Results are saved in `reports/` directory:

```bash
# List reports
ls -lt reports/

# View latest report
cat reports/section_1_*.json | jq .
```

## Quick Commands Reference

```bash
# Run all tests interactively
python run_all_tests.py

# Run individual sections
python section_1_prompt_injection.py     # Prompt Injection
python section_2_jailbreak_dan.py        # Jailbreak & DAN
python section_3_data_leakage.py         # Data Leakage
python section_4_toxicity_harm.py        # Toxicity & Harm
python section_5_encoding_attacks.py     # Encoding Attacks

# Check backend health
curl http://localhost:8888/health

# View API docs
open http://localhost:8888/api/docs
```

## Troubleshooting

**Backend not responding?**
```bash
# Check if backend is running
lsof -i :8888

# Start backend
cd /Users/innox/projects/garak/hydra/backend
python main.py
```

**Open WebUI not accessible?**
```bash
# Check if Open WebUI is running
lsof -i :3030

# Test API key
curl -H "Authorization: Bearer sk-15bdf48030cd4a7e8ee6d98e2ff3faa2" \
  http://localhost:3030/api/v1/models
```

## Next Steps

1. ✅ Run Section 1 (Prompt Injection) first
2. ✅ Review the generated report in `reports/`
3. ✅ Run other sections based on priority
4. ✅ Review comprehensive README.md for advanced usage

---

**Ready?** Run: `python run_all_tests.py`
