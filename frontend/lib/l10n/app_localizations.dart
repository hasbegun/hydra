import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_es.dart';
import 'app_localizations_ja.dart';
import 'app_localizations_ko.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('es'),
    Locale('ja'),
    Locale('ko'),
    Locale('zh'),
  ];

  /// No description provided for @appName.
  ///
  /// In en, this message translates to:
  /// **'Hydra'**
  String get appName;

  /// No description provided for @appDescription.
  ///
  /// In en, this message translates to:
  /// **'LLM Vulnerability Scanner'**
  String get appDescription;

  /// No description provided for @appVersion.
  ///
  /// In en, this message translates to:
  /// **'1.0.0'**
  String get appVersion;

  /// No description provided for @settings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// No description provided for @selectModel.
  ///
  /// In en, this message translates to:
  /// **'Select Model'**
  String get selectModel;

  /// No description provided for @selectProbes.
  ///
  /// In en, this message translates to:
  /// **'Select Probes'**
  String get selectProbes;

  /// No description provided for @advancedConfiguration.
  ///
  /// In en, this message translates to:
  /// **'Advanced Configuration'**
  String get advancedConfiguration;

  /// No description provided for @browseProbes.
  ///
  /// In en, this message translates to:
  /// **'Browse Probes'**
  String get browseProbes;

  /// No description provided for @scanExecution.
  ///
  /// In en, this message translates to:
  /// **'Scan Execution'**
  String get scanExecution;

  /// No description provided for @scanResults.
  ///
  /// In en, this message translates to:
  /// **'Scan Results'**
  String get scanResults;

  /// No description provided for @detailedReport.
  ///
  /// In en, this message translates to:
  /// **'Detailed Report'**
  String get detailedReport;

  /// No description provided for @scanHistory.
  ///
  /// In en, this message translates to:
  /// **'Scan History'**
  String get scanHistory;

  /// No description provided for @myCustomProbes.
  ///
  /// In en, this message translates to:
  /// **'My Custom Probes'**
  String get myCustomProbes;

  /// No description provided for @actions.
  ///
  /// In en, this message translates to:
  /// **'Actions'**
  String get actions;

  /// No description provided for @scan.
  ///
  /// In en, this message translates to:
  /// **'Scan'**
  String get scan;

  /// No description provided for @startNewScan.
  ///
  /// In en, this message translates to:
  /// **'Start a new scan'**
  String get startNewScan;

  /// No description provided for @browseProbesAction.
  ///
  /// In en, this message translates to:
  /// **'Browse Probes'**
  String get browseProbesAction;

  /// No description provided for @viewAllTests.
  ///
  /// In en, this message translates to:
  /// **'View all tests'**
  String get viewAllTests;

  /// No description provided for @writeProbe.
  ///
  /// In en, this message translates to:
  /// **'Write Probe'**
  String get writeProbe;

  /// No description provided for @createCustomProbe.
  ///
  /// In en, this message translates to:
  /// **'Create custom probe'**
  String get createCustomProbe;

  /// No description provided for @myProbes.
  ///
  /// In en, this message translates to:
  /// **'My Probes'**
  String get myProbes;

  /// No description provided for @manageSavedProbes.
  ///
  /// In en, this message translates to:
  /// **'Manage saved probes'**
  String get manageSavedProbes;

  /// No description provided for @history.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get history;

  /// No description provided for @pastScans.
  ///
  /// In en, this message translates to:
  /// **'Past scans'**
  String get pastScans;

  /// No description provided for @recentScans.
  ///
  /// In en, this message translates to:
  /// **'Recent Scans'**
  String get recentScans;

  /// No description provided for @viewAll.
  ///
  /// In en, this message translates to:
  /// **'View All'**
  String get viewAll;

  /// No description provided for @llmVulnerabilityScanner.
  ///
  /// In en, this message translates to:
  /// **'LLM Vulnerability Scanner'**
  String get llmVulnerabilityScanner;

  /// No description provided for @scanDescription.
  ///
  /// In en, this message translates to:
  /// **'Scan your language models for vulnerabilities including jailbreaks, prompt injection, toxicity, and more.'**
  String get scanDescription;

  /// No description provided for @poweredByGarak.
  ///
  /// In en, this message translates to:
  /// **'Powered by Garak'**
  String get poweredByGarak;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @reset.
  ///
  /// In en, this message translates to:
  /// **'Reset'**
  String get reset;

  /// No description provided for @testConnection.
  ///
  /// In en, this message translates to:
  /// **'Test Connection'**
  String get testConnection;

  /// No description provided for @resetToDefaults.
  ///
  /// In en, this message translates to:
  /// **'Reset to Defaults'**
  String get resetToDefaults;

  /// No description provided for @saveSettings.
  ///
  /// In en, this message translates to:
  /// **'Save Settings'**
  String get saveSettings;

  /// No description provided for @continueToProbeSelection.
  ///
  /// In en, this message translates to:
  /// **'Continue to Probe Selection'**
  String get continueToProbeSelection;

  /// No description provided for @clear.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get clear;

  /// No description provided for @advanced.
  ///
  /// In en, this message translates to:
  /// **'Advanced'**
  String get advanced;

  /// No description provided for @quickStart.
  ///
  /// In en, this message translates to:
  /// **'Quick Start'**
  String get quickStart;

  /// No description provided for @goBack.
  ///
  /// In en, this message translates to:
  /// **'Go Back'**
  String get goBack;

  /// No description provided for @cancelScan.
  ///
  /// In en, this message translates to:
  /// **'Cancel Scan'**
  String get cancelScan;

  /// No description provided for @viewResults.
  ///
  /// In en, this message translates to:
  /// **'View Results'**
  String get viewResults;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @backToHome.
  ///
  /// In en, this message translates to:
  /// **'Back to Home'**
  String get backToHome;

  /// No description provided for @newProbe.
  ///
  /// In en, this message translates to:
  /// **'New Probe'**
  String get newProbe;

  /// No description provided for @validate.
  ///
  /// In en, this message translates to:
  /// **'Validate'**
  String get validate;

  /// No description provided for @gotIt.
  ///
  /// In en, this message translates to:
  /// **'Got it'**
  String get gotIt;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @no.
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get no;

  /// No description provided for @yesCancelScan.
  ///
  /// In en, this message translates to:
  /// **'Yes, Cancel'**
  String get yesCancelScan;

  /// No description provided for @stay.
  ///
  /// In en, this message translates to:
  /// **'Stay'**
  String get stay;

  /// No description provided for @ok.
  ///
  /// In en, this message translates to:
  /// **'OK'**
  String get ok;

  /// No description provided for @resetSettings.
  ///
  /// In en, this message translates to:
  /// **'Reset Settings'**
  String get resetSettings;

  /// No description provided for @resetSettingsConfirm.
  ///
  /// In en, this message translates to:
  /// **'Reset all settings to default values?'**
  String get resetSettingsConfirm;

  /// No description provided for @connectionTroubleshooting.
  ///
  /// In en, this message translates to:
  /// **'Connection Troubleshooting'**
  String get connectionTroubleshooting;

  /// No description provided for @apiKeyInformation.
  ///
  /// In en, this message translates to:
  /// **'API Key Information'**
  String get apiKeyInformation;

  /// No description provided for @apiKeyInfoContent.
  ///
  /// In en, this message translates to:
  /// **'The API key is optional here. If you\'ve already set the API key as an environment variable on your system, you don\'t need to enter it again. This field is only needed if you want to override the environment variable.'**
  String get apiKeyInfoContent;

  /// No description provided for @aboutProbes.
  ///
  /// In en, this message translates to:
  /// **'About Probes'**
  String get aboutProbes;

  /// No description provided for @aboutProbesContent.
  ///
  /// In en, this message translates to:
  /// **'Probes are test modules that check for specific vulnerabilities in language models. Each probe contains multiple prompts designed to evaluate how well the model handles potentially harmful inputs.'**
  String get aboutProbesContent;

  /// No description provided for @cancelScanConfirm.
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to cancel this scan?'**
  String get cancelScanConfirm;

  /// No description provided for @scanInProgress.
  ///
  /// In en, this message translates to:
  /// **'Scan in Progress'**
  String get scanInProgress;

  /// No description provided for @scanInProgressContent.
  ///
  /// In en, this message translates to:
  /// **'A scan is currently running. Would you like to cancel it?'**
  String get scanInProgressContent;

  /// No description provided for @exportSuccessful.
  ///
  /// In en, this message translates to:
  /// **'Export Successful'**
  String get exportSuccessful;

  /// No description provided for @detailedScanReport.
  ///
  /// In en, this message translates to:
  /// **'Detailed Scan Report'**
  String get detailedScanReport;

  /// No description provided for @deleteProbe.
  ///
  /// In en, this message translates to:
  /// **'Delete Probe'**
  String get deleteProbe;

  /// No description provided for @deleteProbeConfirm.
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to delete this probe? This action cannot be undone.'**
  String get deleteProbeConfirm;

  /// No description provided for @apiBaseUrl.
  ///
  /// In en, this message translates to:
  /// **'API Base URL'**
  String get apiBaseUrl;

  /// No description provided for @apiBaseUrlHint.
  ///
  /// In en, this message translates to:
  /// **'http://localhost:8888/api/v1'**
  String get apiBaseUrlHint;

  /// No description provided for @apiBaseUrlDescription.
  ///
  /// In en, this message translates to:
  /// **'Backend API endpoint for scan operations'**
  String get apiBaseUrlDescription;

  /// No description provided for @generatorType.
  ///
  /// In en, this message translates to:
  /// **'Generator Type'**
  String get generatorType;

  /// No description provided for @modelName.
  ///
  /// In en, this message translates to:
  /// **'Model Name'**
  String get modelName;

  /// No description provided for @modelNameDescription.
  ///
  /// In en, this message translates to:
  /// **'Enter the specific model identifier'**
  String get modelNameDescription;

  /// No description provided for @apiKey.
  ///
  /// In en, this message translates to:
  /// **'API Key'**
  String get apiKey;

  /// No description provided for @apiKeyDescription.
  ///
  /// In en, this message translates to:
  /// **'Optional: Override environment variable API key'**
  String get apiKeyDescription;

  /// No description provided for @apiKeyHint.
  ///
  /// In en, this message translates to:
  /// **'sk-...'**
  String get apiKeyHint;

  /// No description provided for @parallelRequests.
  ///
  /// In en, this message translates to:
  /// **'Parallel Requests'**
  String get parallelRequests;

  /// No description provided for @parallelRequestsHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., 5'**
  String get parallelRequestsHint;

  /// No description provided for @parallelAttempts.
  ///
  /// In en, this message translates to:
  /// **'Parallel Attempts'**
  String get parallelAttempts;

  /// No description provided for @parallelAttemptsHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., 3'**
  String get parallelAttemptsHint;

  /// No description provided for @randomSeed.
  ///
  /// In en, this message translates to:
  /// **'Random Seed'**
  String get randomSeed;

  /// No description provided for @randomSeedHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., 42'**
  String get randomSeedHint;

  /// No description provided for @searchProbes.
  ///
  /// In en, this message translates to:
  /// **'Search probes...'**
  String get searchProbes;

  /// No description provided for @probeName.
  ///
  /// In en, this message translates to:
  /// **'Probe Name'**
  String get probeName;

  /// No description provided for @probeNameHint.
  ///
  /// In en, this message translates to:
  /// **'MyCustomProbe'**
  String get probeNameHint;

  /// No description provided for @descriptionOptional.
  ///
  /// In en, this message translates to:
  /// **'Description (optional)'**
  String get descriptionOptional;

  /// No description provided for @descriptionHint.
  ///
  /// In en, this message translates to:
  /// **'Brief description of what this probe tests'**
  String get descriptionHint;

  /// No description provided for @probeCodeHint.
  ///
  /// In en, this message translates to:
  /// **'# Write your probe code here...'**
  String get probeCodeHint;

  /// No description provided for @searchScans.
  ///
  /// In en, this message translates to:
  /// **'Search scans...'**
  String get searchScans;

  /// No description provided for @connectionError.
  ///
  /// In en, this message translates to:
  /// **'Cannot connect to server. Make sure the backend is running.'**
  String get connectionError;

  /// No description provided for @networkError.
  ///
  /// In en, this message translates to:
  /// **'Network error. Please check your connection.'**
  String get networkError;

  /// No description provided for @timeoutError.
  ///
  /// In en, this message translates to:
  /// **'Request timed out. The server might be slow or unavailable.'**
  String get timeoutError;

  /// No description provided for @authError.
  ///
  /// In en, this message translates to:
  /// **'Authentication failed. Please check your API key.'**
  String get authError;

  /// No description provided for @forbiddenError.
  ///
  /// In en, this message translates to:
  /// **'Access denied. You may not have permission for this action.'**
  String get forbiddenError;

  /// No description provided for @notFoundError.
  ///
  /// In en, this message translates to:
  /// **'Resource not found. It may have been deleted.'**
  String get notFoundError;

  /// No description provided for @serverError.
  ///
  /// In en, this message translates to:
  /// **'Server error. Please try again later.'**
  String get serverError;

  /// No description provided for @noScansFound.
  ///
  /// In en, this message translates to:
  /// **'No scans found. Complete a scan to see history.'**
  String get noScansFound;

  /// No description provided for @settingsSaved.
  ///
  /// In en, this message translates to:
  /// **'Settings saved successfully'**
  String get settingsSaved;

  /// No description provided for @settingsReset.
  ///
  /// In en, this message translates to:
  /// **'Settings reset to defaults'**
  String get settingsReset;

  /// No description provided for @connectionSuccessful.
  ///
  /// In en, this message translates to:
  /// **'Backend connection successful!'**
  String get connectionSuccessful;

  /// No description provided for @testingConnection.
  ///
  /// In en, this message translates to:
  /// **'Testing connection...'**
  String get testingConnection;

  /// No description provided for @selectGeneratorAndModel.
  ///
  /// In en, this message translates to:
  /// **'Please select a generator type and enter a model name'**
  String get selectGeneratorAndModel;

  /// No description provided for @selectAtLeastOneProbe.
  ///
  /// In en, this message translates to:
  /// **'Please select at least one probe or select all'**
  String get selectAtLeastOneProbe;

  /// No description provided for @enterProbeName.
  ///
  /// In en, this message translates to:
  /// **'Please enter a probe name'**
  String get enterProbeName;

  /// No description provided for @enterProbeCode.
  ///
  /// In en, this message translates to:
  /// **'Please enter probe code'**
  String get enterProbeCode;

  /// No description provided for @fixValidationErrors.
  ///
  /// In en, this message translates to:
  /// **'Please fix validation errors before saving'**
  String get fixValidationErrors;

  /// No description provided for @probeCreatedSuccess.
  ///
  /// In en, this message translates to:
  /// **'Probe saved successfully!'**
  String get probeCreatedSuccess;

  /// No description provided for @startingScan.
  ///
  /// In en, this message translates to:
  /// **'Starting scan...'**
  String get startingScan;

  /// No description provided for @darkMode.
  ///
  /// In en, this message translates to:
  /// **'Dark Mode'**
  String get darkMode;

  /// No description provided for @useDarkTheme.
  ///
  /// In en, this message translates to:
  /// **'Use dark theme'**
  String get useDarkTheme;

  /// No description provided for @version.
  ///
  /// In en, this message translates to:
  /// **'Version'**
  String get version;

  /// No description provided for @description.
  ///
  /// In en, this message translates to:
  /// **'Description'**
  String get description;

  /// No description provided for @garakLlmScanner.
  ///
  /// In en, this message translates to:
  /// **'Garak LLM Scanner'**
  String get garakLlmScanner;

  /// No description provided for @testingLlmsVulnerabilities.
  ///
  /// In en, this message translates to:
  /// **'Testing LLMs for vulnerabilities'**
  String get testingLlmsVulnerabilities;

  /// No description provided for @openSource.
  ///
  /// In en, this message translates to:
  /// **'Open Source'**
  String get openSource;

  /// No description provided for @apacheLicense.
  ///
  /// In en, this message translates to:
  /// **'Apache 2.0 License'**
  String get apacheLicense;

  /// No description provided for @connectionGuide.
  ///
  /// In en, this message translates to:
  /// **'Connection Guide'**
  String get connectionGuide;

  /// No description provided for @forAndroidEmulator.
  ///
  /// In en, this message translates to:
  /// **'For Android Emulator:'**
  String get forAndroidEmulator;

  /// No description provided for @useAndroidEmulatorUrl.
  ///
  /// In en, this message translates to:
  /// **'Use http://10.0.2.2:8888/api/v1'**
  String get useAndroidEmulatorUrl;

  /// No description provided for @forIosSimulator.
  ///
  /// In en, this message translates to:
  /// **'For iOS Simulator:'**
  String get forIosSimulator;

  /// No description provided for @useLocalhostUrl.
  ///
  /// In en, this message translates to:
  /// **'Use http://localhost:8888/api/v1'**
  String get useLocalhostUrl;

  /// No description provided for @forDesktopWeb.
  ///
  /// In en, this message translates to:
  /// **'For Desktop/Web:'**
  String get forDesktopWeb;

  /// No description provided for @useDesktopUrl.
  ///
  /// In en, this message translates to:
  /// **'Use http://localhost:8888/api/v1 or http://127.0.0.1:8888/api/v1'**
  String get useDesktopUrl;

  /// No description provided for @selectAllProbes.
  ///
  /// In en, this message translates to:
  /// **'Select All Probes'**
  String get selectAllProbes;

  /// No description provided for @runComprehensiveScan.
  ///
  /// In en, this message translates to:
  /// **'Run comprehensive scan'**
  String get runComprehensiveScan;

  /// No description provided for @allCategories.
  ///
  /// In en, this message translates to:
  /// **'All Categories'**
  String get allCategories;

  /// No description provided for @inactive.
  ///
  /// In en, this message translates to:
  /// **'Inactive'**
  String get inactive;

  /// No description provided for @active.
  ///
  /// In en, this message translates to:
  /// **'Active'**
  String get active;

  /// No description provided for @fullName.
  ///
  /// In en, this message translates to:
  /// **'Full Name'**
  String get fullName;

  /// No description provided for @status.
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get status;

  /// No description provided for @tags.
  ///
  /// In en, this message translates to:
  /// **'Tags'**
  String get tags;

  /// No description provided for @fastScan.
  ///
  /// In en, this message translates to:
  /// **'Fast Scan'**
  String get fastScan;

  /// No description provided for @fastScanDescription.
  ///
  /// In en, this message translates to:
  /// **'Quick scan with essential probes'**
  String get fastScanDescription;

  /// No description provided for @defaultScan.
  ///
  /// In en, this message translates to:
  /// **'Default Scan'**
  String get defaultScan;

  /// No description provided for @defaultScanDescription.
  ///
  /// In en, this message translates to:
  /// **'Balanced scan covering common vulnerabilities'**
  String get defaultScanDescription;

  /// No description provided for @fullScan.
  ///
  /// In en, this message translates to:
  /// **'Full Scan'**
  String get fullScan;

  /// No description provided for @fullScanDescription.
  ///
  /// In en, this message translates to:
  /// **'Comprehensive scan with maximum thoroughness'**
  String get fullScanDescription;

  /// No description provided for @owaspLlmTop10.
  ///
  /// In en, this message translates to:
  /// **'OWASP LLM Top 10'**
  String get owaspLlmTop10;

  /// No description provided for @owaspLlmTop10Description.
  ///
  /// In en, this message translates to:
  /// **'Focus on OWASP LLM Top 10 vulnerabilities'**
  String get owaspLlmTop10Description;

  /// No description provided for @openai.
  ///
  /// In en, this message translates to:
  /// **'OpenAI'**
  String get openai;

  /// No description provided for @huggingFace.
  ///
  /// In en, this message translates to:
  /// **'Hugging Face'**
  String get huggingFace;

  /// No description provided for @replicate.
  ///
  /// In en, this message translates to:
  /// **'Replicate'**
  String get replicate;

  /// No description provided for @cohere.
  ///
  /// In en, this message translates to:
  /// **'Cohere'**
  String get cohere;

  /// No description provided for @anthropic.
  ///
  /// In en, this message translates to:
  /// **'Anthropic'**
  String get anthropic;

  /// No description provided for @litellm.
  ///
  /// In en, this message translates to:
  /// **'LiteLLM'**
  String get litellm;

  /// No description provided for @nvidiaNim.
  ///
  /// In en, this message translates to:
  /// **'NVIDIA NIM'**
  String get nvidiaNim;

  /// No description provided for @ollama.
  ///
  /// In en, this message translates to:
  /// **'Ollama'**
  String get ollama;

  /// No description provided for @ollamaSetup.
  ///
  /// In en, this message translates to:
  /// **'Ollama Setup'**
  String get ollamaSetup;

  /// No description provided for @ollamaInstructions.
  ///
  /// In en, this message translates to:
  /// **'Make sure Ollama is running locally. By default, it runs on port 11434.'**
  String get ollamaInstructions;

  /// No description provided for @popularModels.
  ///
  /// In en, this message translates to:
  /// **'Popular models: llama2, llama3, gemma, mistral, codellama'**
  String get popularModels;

  /// No description provided for @quickPresets.
  ///
  /// In en, this message translates to:
  /// **'Quick Presets'**
  String get quickPresets;

  /// No description provided for @startWithPreset.
  ///
  /// In en, this message translates to:
  /// **'Start with a preset configuration (optional)'**
  String get startWithPreset;

  /// No description provided for @configureTargetModel.
  ///
  /// In en, this message translates to:
  /// **'Configure Target Model'**
  String get configureTargetModel;

  /// No description provided for @selectLlmGenerator.
  ///
  /// In en, this message translates to:
  /// **'Select the LLM generator and model you want to test'**
  String get selectLlmGenerator;

  /// No description provided for @passRate.
  ///
  /// In en, this message translates to:
  /// **'Pass Rate'**
  String get passRate;

  /// No description provided for @totalTests.
  ///
  /// In en, this message translates to:
  /// **'Total Tests'**
  String get totalTests;

  /// No description provided for @shareResults.
  ///
  /// In en, this message translates to:
  /// **'Share Results'**
  String get shareResults;

  /// No description provided for @export.
  ///
  /// In en, this message translates to:
  /// **'Export'**
  String get export;

  /// No description provided for @exportAsJson.
  ///
  /// In en, this message translates to:
  /// **'Export as JSON'**
  String get exportAsJson;

  /// No description provided for @exportAsHtml.
  ///
  /// In en, this message translates to:
  /// **'Export as HTML'**
  String get exportAsHtml;

  /// No description provided for @exportAsPdf.
  ///
  /// In en, this message translates to:
  /// **'Export as PDF'**
  String get exportAsPdf;

  /// No description provided for @errorLoadingResults.
  ///
  /// In en, this message translates to:
  /// **'Error Loading Results'**
  String get errorLoadingResults;

  /// No description provided for @failedToLoadProbes.
  ///
  /// In en, this message translates to:
  /// **'Failed to load probes'**
  String get failedToLoadProbes;

  /// No description provided for @noScanHistory.
  ///
  /// In en, this message translates to:
  /// **'No scan history'**
  String get noScanHistory;

  /// No description provided for @sortByDate.
  ///
  /// In en, this message translates to:
  /// **'Sort by Date'**
  String get sortByDate;

  /// No description provided for @sortByStatus.
  ///
  /// In en, this message translates to:
  /// **'Sort by Status'**
  String get sortByStatus;

  /// No description provided for @sortByName.
  ///
  /// In en, this message translates to:
  /// **'Sort by Name'**
  String get sortByName;

  /// No description provided for @refresh.
  ///
  /// In en, this message translates to:
  /// **'Refresh'**
  String get refresh;

  /// No description provided for @failedToLoadScanHistory.
  ///
  /// In en, this message translates to:
  /// **'Failed to load scan history'**
  String get failedToLoadScanHistory;

  /// No description provided for @noScanHistoryMessage.
  ///
  /// In en, this message translates to:
  /// **'Your completed scans will appear here'**
  String get noScanHistoryMessage;

  /// No description provided for @about.
  ///
  /// In en, this message translates to:
  /// **'About'**
  String get about;

  /// No description provided for @parallelRequestsTooltip.
  ///
  /// In en, this message translates to:
  /// **'Number of concurrent requests to the target model'**
  String get parallelRequestsTooltip;

  /// No description provided for @parallelAttemptsTooltip.
  ///
  /// In en, this message translates to:
  /// **'Number of retry attempts for failed requests'**
  String get parallelAttemptsTooltip;

  /// No description provided for @generationsPerPrompt.
  ///
  /// In en, this message translates to:
  /// **'Generations per Prompt'**
  String get generationsPerPrompt;

  /// No description provided for @generationsPerPromptTooltip.
  ///
  /// In en, this message translates to:
  /// **'Number of test prompts to generate per probe'**
  String get generationsPerPromptTooltip;

  /// No description provided for @evaluationThreshold.
  ///
  /// In en, this message translates to:
  /// **'Evaluation Threshold'**
  String get evaluationThreshold;

  /// No description provided for @evaluationThresholdTooltip.
  ///
  /// In en, this message translates to:
  /// **'Evaluation threshold for marking tests as failures (0.0 to 1.0)'**
  String get evaluationThresholdTooltip;

  /// No description provided for @modelHintOpenai.
  ///
  /// In en, this message translates to:
  /// **'gpt-4, gpt-3.5-turbo, etc.'**
  String get modelHintOpenai;

  /// No description provided for @modelHintHuggingface.
  ///
  /// In en, this message translates to:
  /// **'meta-llama/Llama-2-7b-chat-hf, etc.'**
  String get modelHintHuggingface;

  /// No description provided for @modelHintReplicate.
  ///
  /// In en, this message translates to:
  /// **'meta/llama-2-70b-chat, etc.'**
  String get modelHintReplicate;

  /// No description provided for @modelHintCohere.
  ///
  /// In en, this message translates to:
  /// **'command, command-light, etc.'**
  String get modelHintCohere;

  /// No description provided for @modelHintAnthropic.
  ///
  /// In en, this message translates to:
  /// **'claude-3-opus-20240229, etc.'**
  String get modelHintAnthropic;

  /// No description provided for @modelHintLitellm.
  ///
  /// In en, this message translates to:
  /// **'gpt-4, claude-2, etc.'**
  String get modelHintLitellm;

  /// No description provided for @modelHintNim.
  ///
  /// In en, this message translates to:
  /// **'meta/llama3-70b-instruct, etc.'**
  String get modelHintNim;

  /// No description provided for @modelHintOllama.
  ///
  /// In en, this message translates to:
  /// **'llama2, mistral, codellama, etc.'**
  String get modelHintOllama;

  /// No description provided for @probeResults.
  ///
  /// In en, this message translates to:
  /// **'Probe Results'**
  String get probeResults;

  /// No description provided for @passed.
  ///
  /// In en, this message translates to:
  /// **'Passed'**
  String get passed;

  /// No description provided for @failed.
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get failed;

  /// No description provided for @total.
  ///
  /// In en, this message translates to:
  /// **'Total'**
  String get total;

  /// No description provided for @details.
  ///
  /// In en, this message translates to:
  /// **'Details'**
  String get details;

  /// No description provided for @summary.
  ///
  /// In en, this message translates to:
  /// **'Summary'**
  String get summary;

  /// No description provided for @configuration.
  ///
  /// In en, this message translates to:
  /// **'Configuration'**
  String get configuration;

  /// No description provided for @model.
  ///
  /// In en, this message translates to:
  /// **'Model'**
  String get model;

  /// No description provided for @generator.
  ///
  /// In en, this message translates to:
  /// **'Generator'**
  String get generator;

  /// No description provided for @probesSelected.
  ///
  /// In en, this message translates to:
  /// **'Probes Selected'**
  String get probesSelected;

  /// No description provided for @startTime.
  ///
  /// In en, this message translates to:
  /// **'Start Time'**
  String get startTime;

  /// No description provided for @endTime.
  ///
  /// In en, this message translates to:
  /// **'End Time'**
  String get endTime;

  /// No description provided for @duration.
  ///
  /// In en, this message translates to:
  /// **'Duration'**
  String get duration;

  /// No description provided for @connectionFailed.
  ///
  /// In en, this message translates to:
  /// **'Connection failed'**
  String get connectionFailed;

  /// No description provided for @checkBackendRunning.
  ///
  /// In en, this message translates to:
  /// **'Please check if the backend server is running'**
  String get checkBackendRunning;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @selectLanguage.
  ///
  /// In en, this message translates to:
  /// **'Select Language'**
  String get selectLanguage;

  /// No description provided for @english.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get english;

  /// No description provided for @korean.
  ///
  /// In en, this message translates to:
  /// **'Korean'**
  String get korean;

  /// No description provided for @japanese.
  ///
  /// In en, this message translates to:
  /// **'Japanese'**
  String get japanese;

  /// No description provided for @spanish.
  ///
  /// In en, this message translates to:
  /// **'Spanish'**
  String get spanish;

  /// No description provided for @chinese.
  ///
  /// In en, this message translates to:
  /// **'Chinese'**
  String get chinese;

  /// No description provided for @apiConfiguration.
  ///
  /// In en, this message translates to:
  /// **'API Configuration'**
  String get apiConfiguration;

  /// No description provided for @appearance.
  ///
  /// In en, this message translates to:
  /// **'Appearance'**
  String get appearance;

  /// No description provided for @defaultScanSettings.
  ///
  /// In en, this message translates to:
  /// **'Default Scan Settings'**
  String get defaultScanSettings;

  /// No description provided for @advancedSettings.
  ///
  /// In en, this message translates to:
  /// **'Advanced Settings'**
  String get advancedSettings;

  /// No description provided for @generations.
  ///
  /// In en, this message translates to:
  /// **'Generations'**
  String get generations;

  /// No description provided for @generationsTooltip.
  ///
  /// In en, this message translates to:
  /// **'Number of test prompts to generate per probe. Higher values = more thorough testing.'**
  String get generationsTooltip;

  /// No description provided for @threshold.
  ///
  /// In en, this message translates to:
  /// **'Threshold'**
  String get threshold;

  /// No description provided for @thresholdTooltip.
  ///
  /// In en, this message translates to:
  /// **'Evaluation threshold for marking tests as failures. Lower values = stricter detection.'**
  String get thresholdTooltip;

  /// No description provided for @connectionTimeout.
  ///
  /// In en, this message translates to:
  /// **'Connection Timeout'**
  String get connectionTimeout;

  /// No description provided for @connectionTimeoutTooltip.
  ///
  /// In en, this message translates to:
  /// **'Time to wait for establishing connection with the backend.'**
  String get connectionTimeoutTooltip;

  /// No description provided for @receiveTimeout.
  ///
  /// In en, this message translates to:
  /// **'Receive Timeout'**
  String get receiveTimeout;

  /// No description provided for @receiveTimeoutTooltip.
  ///
  /// In en, this message translates to:
  /// **'Time to wait for response from the backend. Increase for slow networks or large LLM responses.'**
  String get receiveTimeoutTooltip;

  /// No description provided for @wsReconnectDelay.
  ///
  /// In en, this message translates to:
  /// **'WS Reconnect Delay'**
  String get wsReconnectDelay;

  /// No description provided for @wsReconnectDelayTooltip.
  ///
  /// In en, this message translates to:
  /// **'Delay before attempting to reconnect WebSocket after disconnection.'**
  String get wsReconnectDelayTooltip;

  /// No description provided for @targetEndpoint.
  ///
  /// In en, this message translates to:
  /// **'Target Endpoint'**
  String get targetEndpoint;

  /// No description provided for @targetEndpointTooltip.
  ///
  /// In en, this message translates to:
  /// **'URL endpoint for the target LLM service.'**
  String get targetEndpointTooltip;

  /// No description provided for @restartForSettings.
  ///
  /// In en, this message translates to:
  /// **'Restart the app for network settings to take effect.'**
  String get restartForSettings;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'es', 'ja', 'ko', 'zh'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'es':
      return AppLocalizationsEs();
    case 'ja':
      return AppLocalizationsJa();
    case 'ko':
      return AppLocalizationsKo();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
