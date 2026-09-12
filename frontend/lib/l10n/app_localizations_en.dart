// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'Hydra';

  @override
  String get appDescription => 'LLM Vulnerability Scanner';

  @override
  String get appVersion => '1.0.0';

  @override
  String get settings => 'Settings';

  @override
  String get selectModel => 'Select Model';

  @override
  String get selectProbes => 'Select Probes';

  @override
  String get advancedConfiguration => 'Advanced Configuration';

  @override
  String get browseProbes => 'Browse Probes';

  @override
  String get scanExecution => 'Scan Execution';

  @override
  String get scanResults => 'Scan Results';

  @override
  String get detailedReport => 'Detailed Report';

  @override
  String get scanHistory => 'Scan History';

  @override
  String get myCustomProbes => 'My Custom Probes';

  @override
  String get actions => 'Actions';

  @override
  String get scan => 'Scan';

  @override
  String get startNewScan => 'Start a new scan';

  @override
  String get browseProbesAction => 'Browse Probes';

  @override
  String get viewAllTests => 'View all tests';

  @override
  String get writeProbe => 'Write Probe';

  @override
  String get createCustomProbe => 'Create custom probe';

  @override
  String get myProbes => 'My Probes';

  @override
  String get manageSavedProbes => 'Manage saved probes';

  @override
  String get history => 'History';

  @override
  String get pastScans => 'Past scans';

  @override
  String get recentScans => 'Recent Scans';

  @override
  String get viewAll => 'View All';

  @override
  String get llmVulnerabilityScanner => 'LLM Vulnerability Scanner';

  @override
  String get scanDescription =>
      'Scan your language models for vulnerabilities including jailbreaks, prompt injection, toxicity, and more.';

  @override
  String get poweredByGarak => 'Powered by Garak';

  @override
  String get cancel => 'Cancel';

  @override
  String get reset => 'Reset';

  @override
  String get testConnection => 'Test Connection';

  @override
  String get resetToDefaults => 'Reset to Defaults';

  @override
  String get saveSettings => 'Save Settings';

  @override
  String get continueToProbeSelection => 'Continue to Probe Selection';

  @override
  String get clear => 'Clear';

  @override
  String get advanced => 'Advanced';

  @override
  String get quickStart => 'Quick Start';

  @override
  String get goBack => 'Go Back';

  @override
  String get cancelScan => 'Cancel Scan';

  @override
  String get viewResults => 'View Results';

  @override
  String get retry => 'Retry';

  @override
  String get backToHome => 'Back to Home';

  @override
  String get newProbe => 'New Probe';

  @override
  String get validate => 'Validate';

  @override
  String get gotIt => 'Got it';

  @override
  String get delete => 'Delete';

  @override
  String get no => 'No';

  @override
  String get yesCancelScan => 'Yes, Cancel';

  @override
  String get stay => 'Stay';

  @override
  String get ok => 'OK';

  @override
  String get resetSettings => 'Reset Settings';

  @override
  String get resetSettingsConfirm => 'Reset all settings to default values?';

  @override
  String get connectionTroubleshooting => 'Connection Troubleshooting';

  @override
  String get apiKeyInformation => 'API Key Information';

  @override
  String get apiKeyInfoContent =>
      'The API key is optional here. If you\'ve already set the API key as an environment variable on your system, you don\'t need to enter it again. This field is only needed if you want to override the environment variable.';

  @override
  String get aboutProbes => 'About Probes';

  @override
  String get aboutProbesContent =>
      'Probes are test modules that check for specific vulnerabilities in language models. Each probe contains multiple prompts designed to evaluate how well the model handles potentially harmful inputs.';

  @override
  String get cancelScanConfirm => 'Are you sure you want to cancel this scan?';

  @override
  String get scanInProgress => 'Scan in Progress';

  @override
  String get scanInProgressContent =>
      'A scan is currently running. Would you like to cancel it?';

  @override
  String get exportSuccessful => 'Export Successful';

  @override
  String get detailedScanReport => 'Detailed Scan Report';

  @override
  String get deleteProbe => 'Delete Probe';

  @override
  String get deleteProbeConfirm =>
      'Are you sure you want to delete this probe? This action cannot be undone.';

  @override
  String get apiBaseUrl => 'API Base URL';

  @override
  String get apiBaseUrlHint => 'http://localhost:8888/api/v1';

  @override
  String get apiBaseUrlDescription =>
      'Backend API endpoint for scan operations';

  @override
  String get generatorType => 'Generator Type';

  @override
  String get modelName => 'Model Name';

  @override
  String get modelNameDescription => 'Enter the specific model identifier';

  @override
  String get apiKey => 'API Key';

  @override
  String get apiKeyDescription =>
      'Optional: Override environment variable API key';

  @override
  String get apiKeyHint => 'sk-...';

  @override
  String get parallelRequests => 'Parallel Requests';

  @override
  String get parallelRequestsHint => 'e.g., 5';

  @override
  String get parallelAttempts => 'Parallel Attempts';

  @override
  String get parallelAttemptsHint => 'e.g., 3';

  @override
  String get randomSeed => 'Random Seed';

  @override
  String get randomSeedHint => 'e.g., 42';

  @override
  String get searchProbes => 'Search probes...';

  @override
  String get probeName => 'Probe Name';

  @override
  String get probeNameHint => 'MyCustomProbe';

  @override
  String get descriptionOptional => 'Description (optional)';

  @override
  String get descriptionHint => 'Brief description of what this probe tests';

  @override
  String get probeCodeHint => '# Write your probe code here...';

  @override
  String get searchScans => 'Search scans...';

  @override
  String get connectionError =>
      'Cannot connect to server. Make sure the backend is running.';

  @override
  String get networkError => 'Network error. Please check your connection.';

  @override
  String get timeoutError =>
      'Request timed out. The server might be slow or unavailable.';

  @override
  String get authError => 'Authentication failed. Please check your API key.';

  @override
  String get forbiddenError =>
      'Access denied. You may not have permission for this action.';

  @override
  String get notFoundError => 'Resource not found. It may have been deleted.';

  @override
  String get serverError => 'Server error. Please try again later.';

  @override
  String get noScansFound => 'No scans found. Complete a scan to see history.';

  @override
  String get settingsSaved => 'Settings saved successfully';

  @override
  String get settingsReset => 'Settings reset to defaults';

  @override
  String get connectionSuccessful => 'Backend connection successful!';

  @override
  String get testingConnection => 'Testing connection...';

  @override
  String get selectGeneratorAndModel =>
      'Please select a generator type and enter a model name';

  @override
  String get selectAtLeastOneProbe =>
      'Please select at least one probe or select all';

  @override
  String get enterProbeName => 'Please enter a probe name';

  @override
  String get enterProbeCode => 'Please enter probe code';

  @override
  String get fixValidationErrors =>
      'Please fix validation errors before saving';

  @override
  String get probeCreatedSuccess => 'Probe saved successfully!';

  @override
  String get startingScan => 'Starting scan...';

  @override
  String get darkMode => 'Dark Mode';

  @override
  String get useDarkTheme => 'Use dark theme';

  @override
  String get version => 'Version';

  @override
  String get description => 'Description';

  @override
  String get garakLlmScanner => 'Garak LLM Scanner';

  @override
  String get testingLlmsVulnerabilities => 'Testing LLMs for vulnerabilities';

  @override
  String get openSource => 'Open Source';

  @override
  String get apacheLicense => 'Apache 2.0 License';

  @override
  String get connectionGuide => 'Connection Guide';

  @override
  String get forAndroidEmulator => 'For Android Emulator:';

  @override
  String get useAndroidEmulatorUrl => 'Use http://10.0.2.2:8888/api/v1';

  @override
  String get forIosSimulator => 'For iOS Simulator:';

  @override
  String get useLocalhostUrl => 'Use http://localhost:8888/api/v1';

  @override
  String get forDesktopWeb => 'For Desktop/Web:';

  @override
  String get useDesktopUrl =>
      'Use http://localhost:8888/api/v1 or http://127.0.0.1:8888/api/v1';

  @override
  String get selectAllProbes => 'Select All Probes';

  @override
  String get runComprehensiveScan => 'Run comprehensive scan';

  @override
  String get allCategories => 'All Categories';

  @override
  String get inactive => 'Inactive';

  @override
  String get active => 'Active';

  @override
  String get fullName => 'Full Name';

  @override
  String get status => 'Status';

  @override
  String get tags => 'Tags';

  @override
  String get fastScan => 'Fast Scan';

  @override
  String get fastScanDescription => 'Quick scan with essential probes';

  @override
  String get defaultScan => 'Default Scan';

  @override
  String get defaultScanDescription =>
      'Balanced scan covering common vulnerabilities';

  @override
  String get fullScan => 'Full Scan';

  @override
  String get fullScanDescription =>
      'Comprehensive scan with maximum thoroughness';

  @override
  String get owaspLlmTop10 => 'OWASP LLM Top 10';

  @override
  String get owaspLlmTop10Description =>
      'Focus on OWASP LLM Top 10 vulnerabilities';

  @override
  String get openai => 'OpenAI';

  @override
  String get huggingFace => 'Hugging Face';

  @override
  String get replicate => 'Replicate';

  @override
  String get cohere => 'Cohere';

  @override
  String get anthropic => 'Anthropic';

  @override
  String get litellm => 'LiteLLM';

  @override
  String get nvidiaNim => 'NVIDIA NIM';

  @override
  String get ollama => 'Ollama';

  @override
  String get ollamaSetup => 'Ollama Setup';

  @override
  String get ollamaInstructions =>
      'Make sure Ollama is running locally. By default, it runs on port 11434.';

  @override
  String get popularModels =>
      'Popular models: llama2, llama3, gemma, mistral, codellama';

  @override
  String get quickPresets => 'Quick Presets';

  @override
  String get startWithPreset => 'Start with a preset configuration (optional)';

  @override
  String get configureTargetModel => 'Configure Target Model';

  @override
  String get selectLlmGenerator =>
      'Select the LLM generator and model you want to test';

  @override
  String get passRate => 'Pass Rate';

  @override
  String get totalTests => 'Total Tests';

  @override
  String get shareResults => 'Share Results';

  @override
  String get export => 'Export';

  @override
  String get exportAsJson => 'Export as JSON';

  @override
  String get exportAsHtml => 'Export as HTML';

  @override
  String get exportAsPdf => 'Export as PDF';

  @override
  String get errorLoadingResults => 'Error Loading Results';

  @override
  String get failedToLoadProbes => 'Failed to load probes';

  @override
  String get noScanHistory => 'No scan history';

  @override
  String get sortByDate => 'Sort by Date';

  @override
  String get sortByStatus => 'Sort by Status';

  @override
  String get sortByName => 'Sort by Name';

  @override
  String get refresh => 'Refresh';

  @override
  String get failedToLoadScanHistory => 'Failed to load scan history';

  @override
  String get noScanHistoryMessage => 'Your completed scans will appear here';

  @override
  String get about => 'About';

  @override
  String get parallelRequestsTooltip =>
      'Number of concurrent requests to the target model';

  @override
  String get parallelAttemptsTooltip =>
      'Number of retry attempts for failed requests';

  @override
  String get generationsPerPrompt => 'Generations per Prompt';

  @override
  String get generationsPerPromptTooltip =>
      'Number of test prompts to generate per probe';

  @override
  String get evaluationThreshold => 'Evaluation Threshold';

  @override
  String get evaluationThresholdTooltip =>
      'Evaluation threshold for marking tests as failures (0.0 to 1.0)';

  @override
  String get modelHintOpenai => 'gpt-4, gpt-3.5-turbo, etc.';

  @override
  String get modelHintHuggingface => 'meta-llama/Llama-2-7b-chat-hf, etc.';

  @override
  String get modelHintReplicate => 'meta/llama-2-70b-chat, etc.';

  @override
  String get modelHintCohere => 'command, command-light, etc.';

  @override
  String get modelHintAnthropic => 'claude-3-opus-20240229, etc.';

  @override
  String get modelHintLitellm => 'gpt-4, claude-2, etc.';

  @override
  String get modelHintNim => 'meta/llama3-70b-instruct, etc.';

  @override
  String get modelHintOllama => 'llama2, mistral, codellama, etc.';

  @override
  String get probeResults => 'Probe Results';

  @override
  String get passed => 'Passed';

  @override
  String get failed => 'Failed';

  @override
  String get total => 'Total';

  @override
  String get details => 'Details';

  @override
  String get summary => 'Summary';

  @override
  String get configuration => 'Configuration';

  @override
  String get model => 'Model';

  @override
  String get generator => 'Generator';

  @override
  String get probesSelected => 'Probes Selected';

  @override
  String get startTime => 'Start Time';

  @override
  String get endTime => 'End Time';

  @override
  String get duration => 'Duration';

  @override
  String get connectionFailed => 'Connection failed';

  @override
  String get checkBackendRunning =>
      'Please check if the backend server is running';

  @override
  String get language => 'Language';

  @override
  String get selectLanguage => 'Select Language';

  @override
  String get english => 'English';

  @override
  String get korean => 'Korean';

  @override
  String get japanese => 'Japanese';

  @override
  String get spanish => 'Spanish';

  @override
  String get chinese => 'Chinese';

  @override
  String get apiConfiguration => 'API Configuration';

  @override
  String get appearance => 'Appearance';

  @override
  String get defaultScanSettings => 'Default Scan Settings';

  @override
  String get advancedSettings => 'Advanced Settings';

  @override
  String get generations => 'Generations';

  @override
  String get generationsTooltip =>
      'Number of test prompts to generate per probe. Higher values = more thorough testing.';

  @override
  String get threshold => 'Threshold';

  @override
  String get thresholdTooltip =>
      'Evaluation threshold for marking tests as failures. Lower values = stricter detection.';

  @override
  String get connectionTimeout => 'Connection Timeout';

  @override
  String get connectionTimeoutTooltip =>
      'Time to wait for establishing connection with the backend.';

  @override
  String get receiveTimeout => 'Receive Timeout';

  @override
  String get receiveTimeoutTooltip =>
      'Time to wait for response from the backend. Increase for slow networks or large LLM responses.';

  @override
  String get wsReconnectDelay => 'WS Reconnect Delay';

  @override
  String get wsReconnectDelayTooltip =>
      'Delay before attempting to reconnect WebSocket after disconnection.';

  @override
  String get targetEndpoint => 'Target Endpoint';

  @override
  String get targetEndpointTooltip =>
      'URL endpoint for the target LLM service.';

  @override
  String get restartForSettings =>
      'Restart the app for network settings to take effect.';
}
