# Test Suite Status

## ✅ Backend Integration Fixed

The test suite is now properly configured to work with the hydra backend.

### What Was Fixed

1. **Request Format** - Updated `test_config.py` to use correct API schema:
   ```python
   {
       "target_type": "huggingface",  # Standard generator type
       "target_name": "mistral:latest",  # Model name
       "probes": ["probe.name"],
       "generations": 10
   }
   ```

2. **None Handling** - Fixed all section files to handle `None` probe names during initialization

3. **API Verification** - Created `test_backend_api.py` to verify backend connectivity

### Backend Configuration

**Backend API:** http://localhost:8888
**Status:** ✓ Healthy and running
**Garak Version:** v0.13.2
**Python Version:** 3.11.14
**Available Probes:** 178 probes loaded

### Test Configuration

The tests are configured in `test_config.py`:
- **Target Type:** HuggingFace (compatible with Ollama)
- **Model Name:** mistral:latest
- **API Endpoint:** localhost:8888
- **Test Generations:** 10 (configurable per section)

### How to Run

1. **Verify Backend:**
   ```bash
   python test_backend_api.py
   ```

   Expected output: All tests pass ✓

2. **Run Individual Section:**
   ```bash
   python section_1_prompt_injection.py
   ```

3. **Run All Tests:**
   ```bash
   python run_all_tests.py
   ```

### Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Backend API | ✅ Working | Port 8888, all endpoints responding |
| Request Format | ✅ Fixed | Matches ScanConfigRequest schema |
| Section 1 | ✅ Ready | Prompt Injection tests |
| Section 2 | ✅ Ready | Jailbreak & DAN tests |
| Section 3 | ✅ Ready | Data Leakage tests |
| Section 4 | ✅ Ready | Toxicity & Harm tests |
| Section 5 | ✅ Ready | Encoding Attacks tests |
| Master Runner | ✅ Ready | Interactive menu working |

### Known Limitations

1. **Model Selection** - Currently configured for HuggingFace/Ollama models
2. **Open WebUI** - Not directly tested (using Ollama backend instead)
3. **Generations** - Default is 10, increase for more thorough testing

### Next Steps

1. Run `test_backend_api.py` to verify everything is working
2. Start with Section 1 for a quick test: `python section_1_prompt_injection.py`
3. Review generated reports in `reports/` directory
4. Adjust `TEST_GENERATIONS` in `test_config.py` if needed

---

**Last Updated:** 2025-11-20
**Status:** ✅ Ready for Testing
