import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../models/scan_config.dart';
import '../../providers/plugins_provider.dart';
import '../../providers/scan_config_provider.dart';
import '../../services/export_service.dart';
import '../../utils/ui_helpers.dart';
import '../../utils/keyboard_shortcuts.dart';
import '../scan/scan_execution_screen.dart';

/// Advanced configuration screen for buffs, detectors, and parameters
class AdvancedConfigScreen extends ConsumerStatefulWidget {
  const AdvancedConfigScreen({super.key});

  @override
  ConsumerState<AdvancedConfigScreen> createState() => _AdvancedConfigScreenState();
}

class _AdvancedConfigScreenState extends ConsumerState<AdvancedConfigScreen> {
  final Set<String> _selectedBuffs = {};
  final Set<String> _selectedDetectors = {};

  // Advanced parameters
  int? _parallelRequests;
  int? _parallelAttempts;
  int? _seed;
  bool _extendedDetectors = false;
  bool _deprefix = false;
  int _verbose = 0;
  bool _skipUnknown = false;
  bool _buffsIncludeOriginalPrompt = false;
  bool _noReport = false;
  bool _continueOnError = false;
  int? _timeoutPerProbe;
  double? _reportThreshold;
  double? _hitRate;
  bool _collectTiming = false;
  final TextEditingController _seedController = TextEditingController();
  final TextEditingController _parallelRequestsController = TextEditingController();
  final TextEditingController _parallelAttemptsController = TextEditingController();
  final TextEditingController _systemPromptController = TextEditingController();
  final TextEditingController _reportPrefixController = TextEditingController();
  final TextEditingController _outputDirController = TextEditingController();
  final TextEditingController _excludeProbesController = TextEditingController();
  final TextEditingController _excludeDetectorsController = TextEditingController();
  final TextEditingController _configFileController = TextEditingController();

  @override
  void dispose() {
    _seedController.dispose();
    _parallelRequestsController.dispose();
    _parallelAttemptsController.dispose();
    _systemPromptController.dispose();
    _reportPrefixController.dispose();
    _outputDirController.dispose();
    _excludeProbesController.dispose();
    _excludeDetectorsController.dispose();
    _configFileController.dispose();
    super.dispose();
  }

  /// Check if any changes have been made from default state
  bool get _hasUnsavedChanges {
    return _selectedBuffs.isNotEmpty ||
        _selectedDetectors.isNotEmpty ||
        _parallelRequests != null ||
        _parallelAttempts != null ||
        _seed != null ||
        _extendedDetectors != false ||
        _deprefix != false ||
        _verbose != 0 ||
        _skipUnknown != false ||
        _buffsIncludeOriginalPrompt != false ||
        _noReport != false ||
        _continueOnError != false ||
        _timeoutPerProbe != null ||
        _reportThreshold != null ||
        _hitRate != null ||
        _collectTiming != false ||
        _systemPromptController.text.isNotEmpty ||
        _reportPrefixController.text.isNotEmpty ||
        _outputDirController.text.isNotEmpty ||
        _excludeProbesController.text.isNotEmpty ||
        _excludeDetectorsController.text.isNotEmpty ||
        _configFileController.text.isNotEmpty;
  }

  /// Handle back navigation with unsaved changes check
  Future<bool> _onWillPop() async {
    if (_hasUnsavedChanges) {
      return await context.confirmDiscardChanges();
    }
    return true;
  }

  void _startScan() {
    // Update scan config with advanced options
    final config = ref.read(scanConfigProvider);

    if (config == null) {
      context.showError('Configuration error');
      return;
    }

    // Apply buffs
    if (_selectedBuffs.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setBuffs(_selectedBuffs.toList());
    }

    // Apply detectors
    if (_selectedDetectors.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setDetectors(_selectedDetectors.toList());
    }

    // Apply advanced parameters
    if (_parallelRequests != null) {
      ref.read(scanConfigProvider.notifier).setParallelRequests(_parallelRequests!);
    }
    if (_parallelAttempts != null) {
      ref.read(scanConfigProvider.notifier).setParallelAttempts(_parallelAttempts!);
    }
    if (_seed != null) {
      ref.read(scanConfigProvider.notifier).setSeed(_seed!);
    }

    // Apply system prompt
    if (_systemPromptController.text.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setSystemPrompt(_systemPromptController.text);
    }

    // Apply report prefix
    if (_reportPrefixController.text.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setReportPrefix(_reportPrefixController.text);
    }

    // Apply extended detectors
    ref.read(scanConfigProvider.notifier).setExtendedDetectors(_extendedDetectors);

    // Apply deprefix
    ref.read(scanConfigProvider.notifier).setDeprefix(_deprefix);

    // Apply verbose
    ref.read(scanConfigProvider.notifier).setVerbose(_verbose);

    // Apply skip unknown
    ref.read(scanConfigProvider.notifier).setSkipUnknown(_skipUnknown);

    // Apply buffs include original prompt
    ref.read(scanConfigProvider.notifier).setBuffsIncludeOriginalPrompt(_buffsIncludeOriginalPrompt);

    // Apply output directory
    if (_outputDirController.text.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setOutputDir(_outputDirController.text);
    }

    // Apply no report
    ref.read(scanConfigProvider.notifier).setNoReport(_noReport);

    // Apply continue on error
    ref.read(scanConfigProvider.notifier).setContinueOnError(_continueOnError);

    // Apply exclude probes
    if (_excludeProbesController.text.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setExcludeProbes(_excludeProbesController.text);
    }

    // Apply exclude detectors
    if (_excludeDetectorsController.text.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setExcludeDetectors(_excludeDetectorsController.text);
    }

    // Apply timeout per probe
    if (_timeoutPerProbe != null) {
      ref.read(scanConfigProvider.notifier).setTimeoutPerProbe(_timeoutPerProbe);
    }

    // Apply config file
    if (_configFileController.text.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setConfigFile(_configFileController.text);
    }

    // Apply hit rate
    if (_hitRate != null) {
      ref.read(scanConfigProvider.notifier).setHitRate(_hitRate);
    }

    // Apply report threshold
    if (_reportThreshold != null) {
      ref.read(scanConfigProvider.notifier).setReportThreshold(_reportThreshold);
    }

    // Apply collect timing
    ref.read(scanConfigProvider.notifier).setCollectTiming(_collectTiming);

    // Navigate to scan execution
    Navigator.push(
      context,
      UIHelpers.slideRoute(const ScanExecutionScreen()),
    );
  }

  Future<void> _exportConfig() async {
    final config = ref.read(scanConfigProvider);

    if (config == null) {
      context.showError('No configuration to export');
      return;
    }

    // Build complete config with current advanced selections
    final exportConfig = ScanConfig(
      targetType: config.targetType,
      targetName: config.targetName,
      probes: config.probes,
      detectors: _selectedDetectors.isNotEmpty ? _selectedDetectors.toList() : config.detectors,
      buffs: _selectedBuffs.isNotEmpty ? _selectedBuffs.toList() : config.buffs,
      generations: config.generations,
      evalThreshold: config.evalThreshold,
      seed: _seed ?? config.seed,
      parallelRequests: _parallelRequests ?? config.parallelRequests,
      parallelAttempts: _parallelAttempts ?? config.parallelAttempts,
      generatorOptions: config.generatorOptions,
      probeOptions: config.probeOptions,
      reportPrefix: _reportPrefixController.text.isNotEmpty
          ? _reportPrefixController.text
          : config.reportPrefix,
      probeTags: config.probeTags,
      systemPrompt: _systemPromptController.text.isNotEmpty
          ? _systemPromptController.text
          : config.systemPrompt,
      extendedDetectors: _extendedDetectors,
      deprefix: _deprefix,
      verbose: _verbose,
      skipUnknown: _skipUnknown,
      buffsIncludeOriginalPrompt: _buffsIncludeOriginalPrompt,
      outputDir: _outputDirController.text.isNotEmpty
          ? _outputDirController.text
          : config.outputDir,
      noReport: _noReport,
      continueOnError: _continueOnError,
      excludeProbes: _excludeProbesController.text.isNotEmpty
          ? _excludeProbesController.text
          : config.excludeProbes,
      excludeDetectors: _excludeDetectorsController.text.isNotEmpty
          ? _excludeDetectorsController.text
          : config.excludeDetectors,
      timeoutPerProbe: _timeoutPerProbe ?? config.timeoutPerProbe,
      configFile: _configFileController.text.isNotEmpty
          ? _configFileController.text
          : config.configFile,
      hitRate: _hitRate ?? config.hitRate,
      reportThreshold: _reportThreshold ?? config.reportThreshold,
      collectTiming: _collectTiming,
    );

    try {
      await ExportService().shareConfig(exportConfig);
      if (mounted) {
        context.showSuccess('Configuration exported successfully');
      }
    } catch (e) {
      if (mounted) {
        context.showError('Failed to export: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context)!;

    return Shortcuts(
      shortcuts: {
        KeyboardShortcuts.runShortcut: const ShortcutIntent('start_scan'),
        KeyboardShortcuts.exportShortcut: const ShortcutIntent('export'),
      },
      child: Actions(
        actions: {
          ShortcutIntent: ShortcutCallbackAction({
            'start_scan': _startScan,
            'export': _exportConfig,
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
                title: Text(l10n.advancedConfiguration),
                actions: [
                  IconButton(
                    icon: const Icon(Icons.file_download),
                    onPressed: _exportConfig,
                    tooltip: KeyboardShortcuts.formatHint('Export', 'E'),
                  ),
                ],
              ),
        body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Text(
              'Advanced Options',
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Optional: Configure buffs, detectors, and advanced parameters',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppConstants.largePadding),

            // Buffs Section
            _buildBuffsSection(theme),
            const SizedBox(height: AppConstants.defaultPadding),

            // Detectors Section
            _buildDetectorsSection(theme),
            const SizedBox(height: AppConstants.defaultPadding),

            // Advanced Parameters Section
            _buildAdvancedParametersSection(theme, l10n),
            const SizedBox(height: AppConstants.largePadding),

            // Action Buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      final shouldPop = await _onWillPop();
                      if (shouldPop && context.mounted) {
                        Navigator.pop(context);
                      }
                    },
                    icon: const Icon(Icons.arrow_back),
                    label: const Text('Back'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Tooltip(
                    message: '${KeyboardShortcuts.modifierKey}+Enter',
                    child: FilledButton.icon(
                      onPressed: _startScan,
                      icon: const Icon(Icons.rocket_launch),
                      label: const Text('Start Scan'),
                    ),
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

  Widget _buildBuffsSection(ThemeData theme) {
    final buffsAsync = ref.watch(buffsProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(Icons.auto_fix_high, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Buffs (Input Transformations)',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                buffsAsync.when(
                  data: (buffs) => buffs.isEmpty
                      ? const SizedBox.shrink()
                      : TextButton.icon(
                          onPressed: () {
                            setState(() {
                              if (_selectedBuffs.length == buffs.length) {
                                _selectedBuffs.clear();
                              } else {
                                _selectedBuffs.clear();
                                _selectedBuffs.addAll(buffs.map((b) => b.fullName));
                              }
                            });
                          },
                          icon: Icon(_selectedBuffs.length == buffs.length ? Icons.deselect : Icons.select_all),
                          label: Text(_selectedBuffs.length == buffs.length ? 'Clear All' : 'Select All'),
                        ),
                  loading: () => const SizedBox.shrink(),
                  error: (_, __) => const SizedBox.shrink(),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Buffs modify prompts before testing (e.g., paraphrasing, translation)',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            buffsAsync.when(
              data: (buffs) => buffs.isEmpty
                  ? const Text('No buffs available')
                  : Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: buffs.map((buff) {
                        final isSelected = _selectedBuffs.contains(buff.fullName);
                        final cleanName = UIHelpers.stripAnsiCodes(buff.name);
                        return Tooltip(
                          message: buff.description != null
                              ? UIHelpers.stripAnsiCodes(buff.description!)
                              : cleanName,
                          child: FilterChip(
                            label: Text(cleanName),
                            selected: isSelected,
                            onSelected: (selected) {
                              setState(() {
                                if (selected) {
                                  _selectedBuffs.add(buff.fullName);
                                } else {
                                  _selectedBuffs.remove(buff.fullName);
                                }
                              });
                            },
                          ),
                        );
                      }).toList(),
                    ),
              loading: () => const CircularProgressIndicator(),
              error: (error, stack) => Text('Error loading buffs: $error'),
            ),
            if (_selectedBuffs.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                '${_selectedBuffs.length} buff(s) selected',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
            const SizedBox(height: 16),
            SwitchListTile(
              title: const Text('Include Original Prompt'),
              subtitle: const Text('Test original prompt alongside buffed versions'),
              value: _buffsIncludeOriginalPrompt,
              onChanged: (value) => setState(() => _buffsIncludeOriginalPrompt = value),
              secondary: const Icon(Icons.add_circle_outline),
              contentPadding: EdgeInsets.zero,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetectorsSection(ThemeData theme) {
    final detectorsAsync = ref.watch(detectorsProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(Icons.radar, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Detectors',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                detectorsAsync.when(
                  data: (detectors) => detectors.isEmpty
                      ? const SizedBox.shrink()
                      : TextButton.icon(
                          onPressed: () {
                            setState(() {
                              if (_selectedDetectors.length == detectors.length) {
                                _selectedDetectors.clear();
                              } else {
                                _selectedDetectors.clear();
                                _selectedDetectors.addAll(detectors.map((d) => d.fullName));
                              }
                            });
                          },
                          icon: Icon(_selectedDetectors.length == detectors.length ? Icons.deselect : Icons.select_all),
                          label: Text(_selectedDetectors.length == detectors.length ? 'Clear All' : 'Select All'),
                        ),
                  loading: () => const SizedBox.shrink(),
                  error: (_, __) => const SizedBox.shrink(),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Detectors analyze model outputs to identify vulnerabilities',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            detectorsAsync.when(
              data: (detectors) => detectors.isEmpty
                  ? const Text('No detectors available')
                  : Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: detectors.map((detector) {
                        final isSelected = _selectedDetectors.contains(detector.fullName);
                        final cleanName = UIHelpers.stripAnsiCodes(detector.name);
                        return Tooltip(
                          message: detector.description != null
                              ? UIHelpers.stripAnsiCodes(detector.description!)
                              : cleanName,
                          child: FilterChip(
                            label: Text(cleanName),
                            selected: isSelected,
                            onSelected: (selected) {
                              setState(() {
                                if (selected) {
                                  _selectedDetectors.add(detector.fullName);
                                } else {
                                  _selectedDetectors.remove(detector.fullName);
                                }
                              });
                            },
                          ),
                        );
                      }).toList(),
                    ),
              loading: () => const CircularProgressIndicator(),
              error: (error, stack) => Text('Error loading detectors: $error'),
            ),
            if (_selectedDetectors.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                '${_selectedDetectors.length} detector(s) selected',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildAdvancedParametersSection(ThemeData theme, AppLocalizations l10n) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.tune, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Advanced Parameters',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Parallel Requests
            TextField(
              controller: _parallelRequestsController,
              decoration: InputDecoration(
                labelText: l10n.parallelRequests,
                hintText: 'e.g., 5',
                helperText: 'Number of concurrent API requests (1-20, default: 5)',
                errorText: _parallelRequests != null && (_parallelRequests! < 1 || _parallelRequests! > 20)
                    ? 'Must be between 1 and 20'
                    : null,
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.sync),
              ),
              keyboardType: TextInputType.number,
              onChanged: (value) {
                setState(() {
                  _parallelRequests = int.tryParse(value);
                });
              },
            ),
            const SizedBox(height: 16),

            // Parallel Attempts
            TextField(
              controller: _parallelAttemptsController,
              decoration: InputDecoration(
                labelText: l10n.parallelAttempts,
                hintText: 'e.g., 3',
                helperText: 'Number of parallel generation attempts per prompt (1-10, default: 1)',
                errorText: _parallelAttempts != null && (_parallelAttempts! < 1 || _parallelAttempts! > 10)
                    ? 'Must be between 1 and 10'
                    : null,
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.repeat),
              ),
              keyboardType: TextInputType.number,
              onChanged: (value) {
                setState(() {
                  _parallelAttempts = int.tryParse(value);
                });
              },
            ),
            const SizedBox(height: 16),

            // Seed
            TextField(
              controller: _seedController,
              decoration: InputDecoration(
                labelText: l10n.randomSeed,
                hintText: 'e.g., 42',
                helperText: 'Set for reproducible results (any positive integer, optional)',
                errorText: _seed != null && _seed! < 0
                    ? 'Must be a positive number'
                    : null,
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.tag),
              ),
              keyboardType: TextInputType.number,
              onChanged: (value) {
                setState(() {
                  _seed = int.tryParse(value);
                });
              },
            ),
            const SizedBox(height: 16),

            // System Prompt
            TextField(
              controller: _systemPromptController,
              decoration: InputDecoration(
                labelText: 'System Prompt',
                hintText: 'e.g., You are a helpful assistant...',
                helperText: 'Custom system prompt to use when testing the model (optional)',
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.psychology),
                alignLabelWithHint: true,
                counterText: '${_systemPromptController.text.length} characters',
              ),
              maxLines: 3,
              minLines: 2,
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),

            // Report Prefix
            TextField(
              controller: _reportPrefixController,
              decoration: InputDecoration(
                labelText: 'Report Prefix',
                hintText: 'e.g., my-scan-2024',
                helperText: 'Custom prefix for report filenames (optional)',
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.description),
                counterText: '${_reportPrefixController.text.length} characters',
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),

            // Output Directory
            TextField(
              controller: _outputDirController,
              decoration: const InputDecoration(
                labelText: 'Output Directory',
                hintText: 'e.g., /path/to/output',
                helperText: 'Custom directory for scan output files (optional)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.folder_open),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),

            // Exclude Probes
            TextField(
              controller: _excludeProbesController,
              decoration: const InputDecoration(
                labelText: 'Exclude Probes',
                hintText: 'e.g., dan,encoding,gcg',
                helperText: 'Comma-separated probe names to exclude from scan (optional)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.block),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),

            // Exclude Detectors
            TextField(
              controller: _excludeDetectorsController,
              decoration: const InputDecoration(
                labelText: 'Exclude Detectors',
                hintText: 'e.g., toxicity,always.Pass',
                helperText: 'Comma-separated detector names to exclude (optional)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.block_flipped),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),

            // Config File
            TextField(
              controller: _configFileController,
              decoration: const InputDecoration(
                labelText: 'Config File',
                hintText: 'e.g., /path/to/config.yaml',
                helperText: 'Path to a YAML/JSON config file for garak (optional)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.settings_applications),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),

            // Timeout Per Probe
            Row(
              children: [
                Icon(Icons.timer, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Probe Timeout',
                  style: theme.textTheme.bodyLarge,
                ),
                const Spacer(),
                Text(
                  _timeoutPerProbe == null
                      ? 'Default'
                      : '${_timeoutPerProbe}s',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: theme.colorScheme.primary,
                  ),
                ),
              ],
            ),
            Slider(
              value: (_timeoutPerProbe ?? 0).toDouble(),
              min: 0,
              max: 600,
              divisions: 60,
              label: _timeoutPerProbe == null || _timeoutPerProbe == 0
                  ? 'Default'
                  : '${_timeoutPerProbe}s',
              onChanged: (value) {
                setState(() {
                  _timeoutPerProbe = value == 0 ? null : value.toInt();
                });
              },
            ),
            Text(
              'Time limit for each probe (0 = use default)',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),

            // Report Threshold
            Row(
              children: [
                Icon(Icons.filter_alt, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Report Threshold',
                  style: theme.textTheme.bodyLarge,
                ),
                const Spacer(),
                Text(
                  _reportThreshold == null
                      ? 'Default'
                      : _reportThreshold!.toStringAsFixed(2),
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: theme.colorScheme.primary,
                  ),
                ),
              ],
            ),
            Slider(
              value: (_reportThreshold ?? 0).toDouble(),
              min: 0,
              max: 1.0,
              divisions: 20,
              label: _reportThreshold == null || _reportThreshold == 0
                  ? 'Default'
                  : _reportThreshold!.toStringAsFixed(2),
              onChanged: (value) {
                setState(() {
                  _reportThreshold = value == 0 ? null : value;
                });
              },
            ),
            Text(
              'Only report results above this threshold (0 = report all)',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),

            // Hit Rate
            Row(
              children: [
                Icon(Icons.track_changes, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Hit Rate',
                  style: theme.textTheme.bodyLarge,
                ),
                const Spacer(),
                Text(
                  _hitRate == null
                      ? 'Default'
                      : _hitRate!.toStringAsFixed(2),
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: theme.colorScheme.primary,
                  ),
                ),
              ],
            ),
            Slider(
              value: (_hitRate ?? 0).toDouble(),
              min: 0,
              max: 1.0,
              divisions: 20,
              label: _hitRate == null || _hitRate == 0
                  ? 'Default'
                  : _hitRate!.toStringAsFixed(2),
              onChanged: (value) {
                setState(() {
                  _hitRate = value == 0 ? null : value;
                });
              },
            ),
            Text(
              'Stop scanning a probe after this hit rate is reached (0 = no limit)',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),

            // Extended Detectors Toggle
            SwitchListTile(
              title: const Text('Extended Detectors'),
              subtitle: const Text('Run all detectors instead of primary only'),
              value: _extendedDetectors,
              onChanged: (value) => setState(() => _extendedDetectors = value),
              secondary: const Icon(Icons.radar),
              contentPadding: EdgeInsets.zero,
            ),

            // Deprefix Toggle
            SwitchListTile(
              title: const Text('Deprefix'),
              subtitle: const Text('Remove prompt from output before analysis'),
              value: _deprefix,
              onChanged: (value) => setState(() => _deprefix = value),
              secondary: const Icon(Icons.content_cut),
              contentPadding: EdgeInsets.zero,
            ),
            const SizedBox(height: 16),

            // Verbose Level
            Row(
              children: [
                Icon(Icons.bug_report, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Verbosity',
                  style: theme.textTheme.bodyLarge,
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: SegmentedButton<int>(
                    segments: const [
                      ButtonSegment(value: 0, label: Text('Off')),
                      ButtonSegment(value: 1, label: Text('-v')),
                      ButtonSegment(value: 2, label: Text('-vv')),
                      ButtonSegment(value: 3, label: Text('-vvv')),
                    ],
                    selected: {_verbose},
                    onSelectionChanged: (Set<int> selected) {
                      setState(() => _verbose = selected.first);
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Skip Unknown Plugins Toggle
            SwitchListTile(
              title: const Text('Skip Unknown Plugins'),
              subtitle: const Text('Continue scan even if some plugins are missing'),
              value: _skipUnknown,
              onChanged: (value) => setState(() => _skipUnknown = value),
              secondary: const Icon(Icons.skip_next),
              contentPadding: EdgeInsets.zero,
            ),

            // No Report Toggle
            SwitchListTile(
              title: const Text('Skip Report Generation'),
              subtitle: const Text('Run scan without generating report files'),
              value: _noReport,
              onChanged: (value) => setState(() => _noReport = value),
              secondary: const Icon(Icons.description_outlined),
              contentPadding: EdgeInsets.zero,
            ),

            // Continue on Error Toggle
            SwitchListTile(
              title: const Text('Continue on Error'),
              subtitle: const Text('Skip failed probes and continue scanning'),
              value: _continueOnError,
              onChanged: (value) => setState(() => _continueOnError = value),
              secondary: const Icon(Icons.play_arrow),
              contentPadding: EdgeInsets.zero,
            ),

            // Collect Timing Toggle
            SwitchListTile(
              title: const Text('Collect Timing'),
              subtitle: const Text('Record timing metrics for each probe'),
              value: _collectTiming,
              onChanged: (value) => setState(() => _collectTiming = value),
              secondary: const Icon(Icons.speed),
              contentPadding: EdgeInsets.zero,
            ),

            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: theme.colorScheme.primaryContainer.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    color: theme.colorScheme.primary,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Leave fields empty to use default values',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onPrimaryContainer,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
