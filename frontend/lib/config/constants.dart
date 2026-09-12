/// Application constants and configuration
class AppConstants {
  // API Configuration
  static const String apiBaseUrl = 'http://localhost:8888/api/v1';
  static const String wsBaseUrl = 'ws://localhost:8888/api/v1';

  // App Information
  static const String appName = 'Hydra';
  static const String appVersion = '1.0.0';
  static const String appDescription = 'LLM Vulnerability Scanner';

  // Storage Keys
  static const String keyApiUrl = 'api_url';
  static const String keyThemeMode = 'theme_mode';
  static const String keyRecentScans = 'recent_scans';
  static const String keyConnectionTimeout = 'connection_timeout';
  static const String keyReceiveTimeout = 'receive_timeout';
  static const String keyWsReconnectDelay = 'ws_reconnect_delay';
  static const String keyOllamaEndpoint = 'ollama_endpoint';

  // Default Endpoints
  static const String defaultOllamaEndpoint = 'http://127.0.0.1:11434';

  // Timeouts (in seconds)
  static const int connectionTimeout = 30;
  static const int receiveTimeout = 30;
  static const int wsReconnectDelay = 5;

  // Scan Defaults
  static const int defaultGenerations = 10;
  static const double defaultEvalThreshold = 0.5;
  static const int maxGenerations = 500;
  static const int minGenerations = 1;

  // UI Constants
  static const double defaultPadding = 16.0;
  static const double smallPadding = 8.0;
  static const double largePadding = 24.0;
  static const double borderRadius = 12.0;
  static const double cardElevation = 2.0;
}

/// Generator types supported by garak
class GeneratorTypes {
  static const String openai = 'openai';
  static const String huggingface = 'huggingface';
  static const String replicate = 'replicate';
  static const String cohere = 'cohere';
  static const String anthropic = 'anthropic';
  static const String litellm = 'litellm';
  static const String nim = 'nim';
  static const String ollama = 'ollama';
  static const String groq = 'groq';
  static const String mistral = 'mistral';
  static const String azure = 'azure';
  static const String bedrock = 'bedrock';

  static const List<String> all = [
    openai,
    huggingface,
    anthropic,
    cohere,
    groq,
    mistral,
    azure,
    bedrock,
    replicate,
    litellm,
    nim,
    ollama,
  ];

  /// Get display name (non-localized, for technical contexts)
  static String getDisplayName(String type) {
    switch (type) {
      case openai:
        return 'OpenAI';
      case huggingface:
        return 'Hugging Face';
      case replicate:
        return 'Replicate';
      case cohere:
        return 'Cohere';
      case anthropic:
        return 'Anthropic';
      case litellm:
        return 'LiteLLM';
      case nim:
        return 'NVIDIA NIM';
      case ollama:
        return 'Ollama';
      case groq:
        return 'Groq';
      case mistral:
        return 'Mistral AI';
      case azure:
        return 'Azure OpenAI';
      case bedrock:
        return 'AWS Bedrock';
      default:
        return type;
    }
  }
}

/// Configuration presets
class ConfigPresets {
  static const String fast = 'fast';
  static const String defaultPreset = 'default';
  static const String full = 'full';
  static const String owasp = 'owasp';

  static const List<String> all = [
    fast,
    defaultPreset,
    full,
    owasp,
  ];

  static Map<String, dynamic> getPreset(String name) {
    switch (name) {
      case fast:
        return {
          'name': 'Fast Scan',
          'description': 'Quick scan with essential probes',
          'config': {
            'probes': ['dan', 'encoding', 'promptinject'],
            'generations': 5,
            'eval_threshold': 0.5,
          }
        };
      case defaultPreset:
        return {
          'name': 'Default Scan',
          'description': 'Balanced scan covering common vulnerabilities',
          'config': {
            'probes': ['all'],
            'generations': 10,
            'eval_threshold': 0.5,
          }
        };
      case full:
        return {
          'name': 'Full Scan',
          'description': 'Comprehensive scan with maximum thoroughness',
          'config': {
            'probes': ['all'],
            'generations': 25,
            'eval_threshold': 0.3,
            'parallel_attempts': 4,
          }
        };
      case owasp:
        return {
          'name': 'OWASP LLM Top 10',
          'description': 'Focus on OWASP LLM Top 10 vulnerabilities',
          'config': {
            'probes': ['promptinject', 'dan', 'lmrc', 'encoding'],
            'generations': 15,
            'eval_threshold': 0.4,
          }
        };
      default:
        return getPreset(defaultPreset);
    }
  }

  static List<Map<String, dynamic>> getAllPresets() {
    return all.map((name) => getPreset(name)).toList();
  }
}
