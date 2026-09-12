import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../providers/api_provider.dart';
import '../../providers/theme_provider.dart';
import '../../providers/locale_provider.dart';
import '../../utils/ui_helpers.dart';
import '../../utils/keyboard_shortcuts.dart';

/// Settings screen for app configuration
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late TextEditingController _apiUrlController;
  late TextEditingController _ollamaEndpointController;
  bool _isDarkMode = false;
  int _defaultGenerations = AppConstants.defaultGenerations;
  double _defaultThreshold = AppConstants.defaultEvalThreshold;

  // Network settings
  int _connectionTimeout = AppConstants.connectionTimeout;
  int _receiveTimeout = AppConstants.receiveTimeout;
  int _wsReconnectDelay = AppConstants.wsReconnectDelay;

  // Initial values for change detection
  bool _initialDarkMode = false;
  int _initialGenerations = AppConstants.defaultGenerations;
  double _initialThreshold = AppConstants.defaultEvalThreshold;
  String _initialApiUrl = AppConstants.apiBaseUrl;
  int _initialConnectionTimeout = AppConstants.connectionTimeout;
  int _initialReceiveTimeout = AppConstants.receiveTimeout;
  int _initialWsReconnectDelay = AppConstants.wsReconnectDelay;
  String _initialOllamaEndpoint = AppConstants.defaultOllamaEndpoint;
  bool _settingsLoaded = false;

  @override
  void initState() {
    super.initState();
    _apiUrlController = TextEditingController(text: AppConstants.apiBaseUrl);
    _ollamaEndpointController = TextEditingController(text: AppConstants.defaultOllamaEndpoint);
    _loadSettings();
  }

  @override
  void dispose() {
    _apiUrlController.dispose();
    _ollamaEndpointController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final themeMode = ref.read(themeModeProvider);
    setState(() {
      _isDarkMode = themeMode == ThemeMode.dark;
      _defaultGenerations = prefs.getInt('default_generations') ?? AppConstants.defaultGenerations;
      _defaultThreshold = prefs.getDouble('default_threshold') ?? AppConstants.defaultEvalThreshold;
      _apiUrlController.text = prefs.getString('api_url') ?? AppConstants.apiBaseUrl;

      // Network settings
      _connectionTimeout = prefs.getInt(AppConstants.keyConnectionTimeout) ?? AppConstants.connectionTimeout;
      _receiveTimeout = prefs.getInt(AppConstants.keyReceiveTimeout) ?? AppConstants.receiveTimeout;
      _wsReconnectDelay = prefs.getInt(AppConstants.keyWsReconnectDelay) ?? AppConstants.wsReconnectDelay;
      _ollamaEndpointController.text = prefs.getString(AppConstants.keyOllamaEndpoint) ?? AppConstants.defaultOllamaEndpoint;

      // Store initial values for change detection
      _initialDarkMode = _isDarkMode;
      _initialGenerations = _defaultGenerations;
      _initialThreshold = _defaultThreshold;
      _initialApiUrl = _apiUrlController.text;
      _initialConnectionTimeout = _connectionTimeout;
      _initialReceiveTimeout = _receiveTimeout;
      _initialWsReconnectDelay = _wsReconnectDelay;
      _initialOllamaEndpoint = _ollamaEndpointController.text;
      _settingsLoaded = true;
    });
  }

  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final l10n = AppLocalizations.of(context)!;

    // Update theme using theme provider
    await ref.read(themeModeProvider.notifier).setDarkMode(_isDarkMode);

    await prefs.setInt('default_generations', _defaultGenerations);
    await prefs.setDouble('default_threshold', _defaultThreshold);
    await prefs.setString('api_url', _apiUrlController.text);

    // Save network settings
    await prefs.setInt(AppConstants.keyConnectionTimeout, _connectionTimeout);
    await prefs.setInt(AppConstants.keyReceiveTimeout, _receiveTimeout);
    await prefs.setInt(AppConstants.keyWsReconnectDelay, _wsReconnectDelay);
    await prefs.setString(AppConstants.keyOllamaEndpoint, _ollamaEndpointController.text);

    if (mounted) {
      context.showSuccess(l10n.settingsSaved);
      // Update initial values after save
      _initialDarkMode = _isDarkMode;
      _initialGenerations = _defaultGenerations;
      _initialThreshold = _defaultThreshold;
      _initialApiUrl = _apiUrlController.text;
      _initialConnectionTimeout = _connectionTimeout;
      _initialReceiveTimeout = _receiveTimeout;
      _initialWsReconnectDelay = _wsReconnectDelay;
      _initialOllamaEndpoint = _ollamaEndpointController.text;
    }
  }

  /// Check if any settings have changed from their saved values
  bool get _hasUnsavedChanges {
    if (!_settingsLoaded) return false;
    return _isDarkMode != _initialDarkMode ||
        _defaultGenerations != _initialGenerations ||
        _defaultThreshold != _initialThreshold ||
        _apiUrlController.text != _initialApiUrl ||
        _connectionTimeout != _initialConnectionTimeout ||
        _receiveTimeout != _initialReceiveTimeout ||
        _wsReconnectDelay != _initialWsReconnectDelay ||
        _ollamaEndpointController.text != _initialOllamaEndpoint;
  }

  /// Handle back navigation with unsaved changes check
  Future<bool> _onWillPop() async {
    if (_hasUnsavedChanges) {
      return await context.confirmDiscardChanges();
    }
    return true;
  }

  Future<void> _resetToDefaults() async {
    final l10n = AppLocalizations.of(context)!;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.resetSettings),
        content: Text(l10n.resetSettingsConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(l10n.reset),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.clear();

      // Reset theme to light mode
      await ref.read(themeModeProvider.notifier).setDarkMode(false);

      // Reset locale to system default
      await ref.read(localeProvider.notifier).setLocale(null);

      setState(() {
        _isDarkMode = false;
        _defaultGenerations = AppConstants.defaultGenerations;
        _defaultThreshold = AppConstants.defaultEvalThreshold;
        _apiUrlController.text = AppConstants.apiBaseUrl;

        // Reset network settings
        _connectionTimeout = AppConstants.connectionTimeout;
        _receiveTimeout = AppConstants.receiveTimeout;
        _wsReconnectDelay = AppConstants.wsReconnectDelay;
        _ollamaEndpointController.text = AppConstants.defaultOllamaEndpoint;
      });

      if (mounted) {
        context.showSuccess(l10n.settingsReset);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context)!;

    return Shortcuts(
      shortcuts: {
        KeyboardShortcuts.saveShortcut: const ShortcutIntent('save'),
      },
      child: Actions(
        actions: {
          ShortcutIntent: ShortcutCallbackAction({
            'save': _saveSettings,
          }),
        },
        child: Focus(
          autofocus: true,
          child: PopScope(
            canPop: false,
            onPopInvokedWithResult: (didPop, result) async {
              if (didPop) return;
              final shouldPop = await _onWillPop();
              if (shouldPop && context.mounted) {
                Navigator.of(context).pop();
              }
            },
            child: Scaffold(
              appBar: AppBar(
                title: Text(l10n.settings),
                actions: [
                  IconButton(
                    icon: const Icon(Icons.save),
                    onPressed: _saveSettings,
                    tooltip: KeyboardShortcuts.formatHint(l10n.saveSettings, 'S'),
                  ),
                ],
              ),
              body: SingleChildScrollView(
                padding: const EdgeInsets.all(AppConstants.defaultPadding),
                child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // API Configuration Section
            _buildSectionHeader(theme, Icons.cloud, l10n.apiConfiguration),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(AppConstants.defaultPadding),
                child: Column(
                  children: [
                    TextField(
                      controller: _apiUrlController,
                      decoration: InputDecoration(
                        labelText: l10n.apiBaseUrl,
                        hintText: 'http://localhost:8888/api/v1',
                        border: const OutlineInputBorder(),
                        prefixIcon: const Icon(Icons.link),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      l10n.apiBaseUrlDescription,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.primaryContainer.withValues(alpha: 0.3),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: theme.colorScheme.primary.withValues(alpha: 0.3),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.info_outline,
                                size: 16,
                                color: theme.colorScheme.primary,
                              ),
                              const SizedBox(width: 8),
                              Text(
                                l10n.connectionGuide,
                                style: theme.textTheme.titleSmall?.copyWith(
                                  color: theme.colorScheme.onPrimaryContainer,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _getConnectionGuide(),
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onPrimaryContainer,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: _testConnection,
                        icon: const Icon(Icons.wifi_find),
                        label: Text(l10n.testConnection),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppConstants.largePadding),

            // Advanced Settings Section
            _buildSectionHeader(theme, Icons.tune, l10n.advancedSettings),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(AppConstants.defaultPadding),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Connection Timeout
                    Row(
                      children: [
                        Text(
                          '${l10n.connectionTimeout}: ${_connectionTimeout}s',
                          style: theme.textTheme.titleSmall,
                        ),
                        const SizedBox(width: 8),
                        UIHelpers.buildTooltip(
                          message: l10n.connectionTimeoutTooltip,
                          child: Icon(
                            Icons.info_outline,
                            size: 16,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                    Slider(
                      value: _connectionTimeout.toDouble(),
                      min: 5,
                      max: 120,
                      divisions: 23,
                      label: '${_connectionTimeout}s',
                      onChanged: (value) {
                        setState(() {
                          _connectionTimeout = value.toInt();
                        });
                      },
                    ),
                    const SizedBox(height: 16),

                    // Receive Timeout
                    Row(
                      children: [
                        Text(
                          '${l10n.receiveTimeout}: ${_receiveTimeout}s',
                          style: theme.textTheme.titleSmall,
                        ),
                        const SizedBox(width: 8),
                        UIHelpers.buildTooltip(
                          message: l10n.receiveTimeoutTooltip,
                          child: Icon(
                            Icons.info_outline,
                            size: 16,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                    Slider(
                      value: _receiveTimeout.toDouble(),
                      min: 5,
                      max: 300,
                      divisions: 59,
                      label: '${_receiveTimeout}s',
                      onChanged: (value) {
                        setState(() {
                          _receiveTimeout = value.toInt();
                        });
                      },
                    ),
                    const SizedBox(height: 16),

                    // WebSocket Reconnect Delay
                    Row(
                      children: [
                        Text(
                          '${l10n.wsReconnectDelay}: ${_wsReconnectDelay}s',
                          style: theme.textTheme.titleSmall,
                        ),
                        const SizedBox(width: 8),
                        UIHelpers.buildTooltip(
                          message: l10n.wsReconnectDelayTooltip,
                          child: Icon(
                            Icons.info_outline,
                            size: 16,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                    Slider(
                      value: _wsReconnectDelay.toDouble(),
                      min: 1,
                      max: 30,
                      divisions: 29,
                      label: '${_wsReconnectDelay}s',
                      onChanged: (value) {
                        setState(() {
                          _wsReconnectDelay = value.toInt();
                        });
                      },
                    ),
                    const SizedBox(height: 16),

                    // Target Endpoint
                    Row(
                      children: [
                        Text(
                          l10n.targetEndpoint,
                          style: theme.textTheme.titleSmall,
                        ),
                        const SizedBox(width: 8),
                        UIHelpers.buildTooltip(
                          message: l10n.targetEndpointTooltip,
                          child: Icon(
                            Icons.info_outline,
                            size: 16,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _ollamaEndpointController,
                      decoration: InputDecoration(
                        hintText: AppConstants.defaultOllamaEndpoint,
                        border: const OutlineInputBorder(),
                        prefixIcon: const Icon(Icons.dns),
                        isDense: true,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.secondaryContainer.withValues(alpha: 0.3),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            Icons.info_outline,
                            size: 16,
                            color: theme.colorScheme.onSecondaryContainer,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              l10n.restartForSettings,
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSecondaryContainer,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppConstants.largePadding),

            // Default Scan Settings Section
            _buildSectionHeader(theme, Icons.settings, l10n.defaultScanSettings),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(AppConstants.defaultPadding),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          '${l10n.generations}: $_defaultGenerations',
                          style: theme.textTheme.titleSmall,
                        ),
                        const SizedBox(width: 8),
                        UIHelpers.buildTooltip(
                          message: l10n.generationsTooltip,
                          child: Icon(
                            Icons.info_outline,
                            size: 16,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                    Slider(
                      value: _defaultGenerations.toDouble(),
                      min: AppConstants.minGenerations.toDouble(),
                      max: AppConstants.maxGenerations.toDouble(),
                      divisions: AppConstants.maxGenerations - AppConstants.minGenerations,
                      label: _defaultGenerations.toString(),
                      onChanged: (value) {
                        setState(() {
                          _defaultGenerations = value.toInt();
                        });
                      },
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Text(
                          '${l10n.threshold}: ${_defaultThreshold.toStringAsFixed(2)}',
                          style: theme.textTheme.titleSmall,
                        ),
                        const SizedBox(width: 8),
                        UIHelpers.buildTooltip(
                          message: l10n.thresholdTooltip,
                          child: Icon(
                            Icons.info_outline,
                            size: 16,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                    Slider(
                      value: _defaultThreshold,
                      min: 0.0,
                      max: 1.0,
                      divisions: 20,
                      label: _defaultThreshold.toStringAsFixed(2),
                      onChanged: (value) {
                        setState(() {
                          _defaultThreshold = value;
                        });
                      },
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppConstants.largePadding),

            // Appearance Section
            _buildSectionHeader(theme, Icons.palette, l10n.appearance),
            Card(
              child: Column(
                children: [
                  SwitchListTile(
                    title: Text(l10n.darkMode),
                    subtitle: Text(l10n.useDarkTheme),
                    value: _isDarkMode,
                    onChanged: (value) {
                      setState(() {
                        _isDarkMode = value;
                      });
                    },
                    secondary: Icon(
                      _isDarkMode ? Icons.dark_mode : Icons.light_mode,
                    ),
                  ),
                  const Divider(),
                  _buildLanguageSelector(theme, l10n),
                ],
              ),
            ),
            const SizedBox(height: AppConstants.largePadding),

            // Actions Section
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _resetToDefaults,
                    icon: const Icon(Icons.restore),
                    label: Text(l10n.resetToDefaults),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _saveSettings,
                    icon: const Icon(Icons.save),
                    label: Text(l10n.saveSettings),
                  ),
                ),
              ],
            ),
          ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLanguageSelector(ThemeData theme, AppLocalizations l10n) {
    final currentLocale = ref.watch(localeProvider);
    final currentLanguageName = LocaleNotifier.getDisplayName(currentLocale);

    return ListTile(
      leading: const Icon(Icons.language),
      title: Text(l10n.language),
      subtitle: Text(currentLanguageName),
      trailing: const Icon(Icons.arrow_drop_down),
      onTap: () {
        showDialog(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: Text(l10n.language),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _buildLanguageOption(dialogContext, null, currentLocale),
                  ...LocaleNotifier.availableLocales.map(
                    (locale) => _buildLanguageOption(dialogContext, locale, currentLocale),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildLanguageOption(BuildContext dialogContext, Locale? locale, Locale? currentLocale) {
    final isSelected = locale?.languageCode == currentLocale?.languageCode;
    final name = LocaleNotifier.getDisplayName(locale);

    return ListTile(
      title: Text(name),
      trailing: isSelected ? Icon(Icons.check, color: Theme.of(context).colorScheme.primary) : null,
      onTap: () async {
        await ref.read(localeProvider.notifier).setLocale(locale);
        if (dialogContext.mounted) {
          Navigator.pop(dialogContext);
        }
      },
    );
  }

  Widget _buildSectionHeader(ThemeData theme, IconData icon, String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(icon, color: theme.colorScheme.primary, size: 20),
          const SizedBox(width: 8),
          Text(
            title,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: theme.colorScheme.primary,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _testConnection() async {
    final l10n = AppLocalizations.of(context)!;

    try {
      context.showLoading(message: l10n.testingConnection);
      final apiService = ref.read(apiServiceProvider);
      await apiService.healthCheck();
      if (mounted) {
        context.dismissLoading();
        context.showSuccess(l10n.connectionSuccessful);
      }
    } catch (e) {
      if (mounted) {
        context.dismissLoading();
        context.showError(
          'Connection failed: ${e.toString()}',
          action: 'Help',
          onAction: () => _showConnectionHelp(),
        );
      }
    }
  }

  void _showConnectionHelp() {
    final l10n = AppLocalizations.of(context)!;

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.connectionTroubleshooting),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Common Issues:',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              const Text('1. Backend not running'),
              const Text('   -> Start backend: python main.py'),
              const SizedBox(height: 8),
              const Text('2. Wrong URL for platform'),
              Text('   -> ${_getConnectionGuide().split('\n')[1]}'),
              const SizedBox(height: 8),
              const Text('3. Firewall blocking connection'),
              const Text('   -> Check firewall settings'),
              const SizedBox(height: 8),
              const Text('4. Backend on different port'),
              const Text('   -> Check backend logs for port'),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(l10n.gotIt),
          ),
        ],
      ),
    );
  }

  String _getConnectionGuide() {
    if (!kIsWeb && Platform.isAndroid) {
      return '''For Android Emulator:
* Use http://10.0.2.2:8888/api/v1
* localhost is automatically converted to 10.0.2.2

For Physical Device:
* Use your computer's IP address
* Example: http://192.168.1.100:8888/api/v1
* Make sure backend is running on 0.0.0.0:8888''';
    } else if (!kIsWeb && Platform.isIOS) {
      return '''For iOS Simulator:
* Use http://localhost:8888/api/v1
* Or http://127.0.0.1:8888/api/v1

For Physical Device:
* Use your computer's IP address
* Example: http://192.168.1.100:8888/api/v1
* Make sure backend is running on 0.0.0.0:8888''';
    } else {
      return '''For Desktop/Web:
* Use http://localhost:8888/api/v1
* Make sure the backend is running

Backend command:
cd garak_backend && python main.py''';
    }
  }

}
