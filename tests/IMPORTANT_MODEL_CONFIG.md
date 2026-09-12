# Important: Model Configuration Issue

## Current Status

⚠️ **The test suite has a model configuration issue that prevents tests from running.**

### The Problem

The hydra backend currently expects standard LLM provider configurations (OpenAI, HuggingFace, Anthropic), but we're trying to test:
- **Target:** Open WebUI (localhost:3030)
- **Backend:** Ollama
- **Model:** mistral:latest

The current configuration uses:
```python
{
    "target_type": "huggingface",  # Wrong: should be for Ollama
    "target_name": "mistral:latest",  # Ollama model name, not HuggingFace
    ...
}
```

**Result:** Scans complete in 1-2 seconds with **0 tests run**.

## Solutions

### Option 1: Test Ollama Directly (Recommended)

Update `test_config.py` to use Ollama's API directly:

```python
# In test_config.py
def get_scan_config(probes: list, generations: int = None) -> Dict[str, Any]:
    return {
        "target_type": "litellm",  # LiteLLM can proxy to Ollama
        "target_name": "ollama/mistral:latest",
        "probes": probes,
        "generations": generations,
        "generator_options": {
            "api_base": "http://localhost:11434"  # Ollama's default port
        }
    }
```

### Option 2: Use Garak CLI Directly

Bypass the hydra backend and use Garak CLI with the original REST configuration:

```bash
cd /Users/innox/projects/garak
python -m garak \
  --model_type rest \
  --model_name "mistral via OpenWebUI" \
  --probes promptinject.HijackKillHumans \
  --probes promptinject.HijackHateHumans \
  --generations 10 \
  --rest_endpoint http://localhost:3030/api/v1/chat/completions \
  --rest_headers '{"Authorization": "Bearer sk-15bdf48030cd4a7e8ee6d98e2ff3faa2"}' \
  --rest_body_template '{"model": "mistral:latest", "messages": [{"role": "user", "content": "$INPUT"}], "stream": false}' \
  --rest_response_json_field "choices[0].message.content"
```

### Option 3: Update Backend to Support REST

Modify the hydra backend `/models/schemas.py` to add REST as a generator type:

```python
class GeneratorType(str, Enum):
    """Supported generator types"""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    REPLICATE = "replicate"
    COHERE = "cohere"
    ANTHROPIC = "anthropic"
    LITELLM = "litellm"
    NIM = "nim"
    REST = "rest"  # Add this
```

Then update the backend to handle REST configuration.

## Immediate Workaround

For now, the test suite is configured but **won't run actual tests** because of this model config issue.

To verify the test structure works, you can test with a real LLM provider:

```bash
# Set environment variable for a real model
export OLLAMA_MODEL="gpt-3.5-turbo"  # If you have OpenAI
export OPENAI_API_KEY="sk-..."

# Update test_config.py temporarily
{
    "target_type": "openai",
    "target_name": "gpt-3.5-turbo",
    ...
}
```

## Status

- ✅ Test suite structure: **Working**
- ✅ Backend API: **Working**
- ✅ Probe names: **Fixed**
- ✅ Monitoring: **Fixed**
- ❌ Model configuration: **Needs fix**

## Recommendation

**Option 2 (Garak CLI directly)** is the quickest solution. The test suite in `/Users/innox/projects/garak/tests/` uses this approach and should work correctly.

Consider using that test suite instead:
```bash
cd /Users/innox/projects/garak/tests
python run_manual_tests.py
```

---

**Created:** 2025-11-20
**Issue:** Model configuration incompatibility
**Impact:** Tests run but execute 0 test cases
