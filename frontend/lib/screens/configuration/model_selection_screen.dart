import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../providers/scan_config_provider.dart';
import '../../providers/models_provider.dart';
import '../../providers/api_provider.dart';
import '../../models/generator_model.dart';
import '../../utils/ui_helpers.dart';
import '../configuration/probe_selection_screen.dart';

class ModelSelectionScreen extends ConsumerStatefulWidget {
  final String? initialPreset;

  const ModelSelectionScreen({
    super.key,
    this.initialPreset,
  });

  @override
  ConsumerState<ModelSelectionScreen> createState() => _ModelSelectionScreenState();
}

class _ModelSelectionScreenState extends ConsumerState<ModelSelectionScreen> {
  String? _selectedGeneratorType;
  String? _selectedPreset;
  String _ollamaEndpoint = AppConstants.defaultOllamaEndpoint;
  final TextEditingController _modelNameController = TextEditingController();
  final TextEditingController _apiKeyController = TextEditingController();
  String? _selectedModelId; // Track the actual model ID for backend

  // API key validation state
  bool _isValidatingApiKey = false;
  bool? _apiKeyValid;
  String? _apiKeyValidationMessage;

  @override
  void initState() {
    super.initState();
    _loadOllamaEndpoint();
    // Set initial preset if provided
    if (widget.initialPreset != null) {
      _selectedPreset = widget.initialPreset;
      // Auto-apply preset on initialization
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_selectedPreset != null) {
          _applyPreset(_selectedPreset!);
        }
      });
    }
  }

  Future<void> _loadOllamaEndpoint() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _ollamaEndpoint = prefs.getString(AppConstants.keyOllamaEndpoint) ?? AppConstants.defaultOllamaEndpoint;
    });
  }

  @override
  void dispose() {
    _modelNameController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  void _applyPreset(String presetKey) {
    // Preset will be applied when continuing to probe selection
    // This just marks it as selected for now
    context.showInfo('${ConfigPresets.getPreset(presetKey)['name']} preset selected');
  }

  void _continueToProbeSelection() {
    final l10n = AppLocalizations.of(context)!;
    if (_selectedGeneratorType == null || _modelNameController.text.isEmpty) {
      context.showError(l10n.selectGeneratorAndModel);
      return;
    }

    // Update scan config - use model ID if available, otherwise use text field value
    final modelIdentifier = _selectedModelId ?? _modelNameController.text;
    ref.read(scanConfigProvider.notifier).setTarget(
          _selectedGeneratorType!,
          modelIdentifier,
        );

    // Apply preset if selected
    if (_selectedPreset != null) {
      ref.read(scanConfigProvider.notifier).loadPreset(
        ConfigPresets.getPreset(_selectedPreset!),
      );
    }

    // Set API key if provided
    if (_apiKeyController.text.isNotEmpty) {
      ref.read(scanConfigProvider.notifier).setGeneratorOptions({
        'api_key': _apiKeyController.text,
      });
    }

    // Navigate to probe selection
    Navigator.push(
      context,
      UIHelpers.slideRoute(const ProbeSelectionScreen()),
    );
  }

  Future<void> _validateApiKey() async {
    if (_selectedGeneratorType == null || _apiKeyController.text.isEmpty) {
      return;
    }

    setState(() {
      _isValidatingApiKey = true;
      _apiKeyValid = null;
      _apiKeyValidationMessage = null;
    });

    try {
      final apiService = ref.read(apiServiceProvider);
      final result = await apiService.validateApiKey(
        _selectedGeneratorType!,
        _apiKeyController.text,
      );

      if (mounted) {
        setState(() {
          _isValidatingApiKey = false;
          _apiKeyValid = result.valid;
          _apiKeyValidationMessage = result.message;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isValidatingApiKey = false;
          _apiKeyValid = false;
          _apiKeyValidationMessage = 'Validation error: $e';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.selectModel),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppConstants.defaultPadding),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Text(
                l10n.configureTargetModel,
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                l10n.selectLlmGenerator,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: AppConstants.largePadding),

              // Preset Selection
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppConstants.defaultPadding),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.stars, color: theme.colorScheme.primary),
                          const SizedBox(width: 8),
                          Text(
                            l10n.quickPresets,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Start with a preset configuration (optional)',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: AppConstants.defaultPadding),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: ConfigPresets.all.map((presetKey) {
                          final preset = ConfigPresets.getPreset(presetKey);
                          final isSelected = _selectedPreset == presetKey;
                          return ChoiceChip(
                            label: Text(preset['name'] as String),
                            selected: isSelected,
                            onSelected: (selected) {
                              setState(() {
                                _selectedPreset = selected ? presetKey : null;
                                if (selected) {
                                  _applyPreset(presetKey);
                                }
                              });
                            },
                          );
                        }).toList(),
                      ),
                      if (_selectedPreset != null) ...[
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.primaryContainer.withValues(alpha: 0.3),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            ConfigPresets.getPreset(_selectedPreset!)['description'] as String,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onPrimaryContainer,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              const SizedBox(height: AppConstants.defaultPadding),

              // Generator Type Selection
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppConstants.defaultPadding),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l10n.generatorType,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: AppConstants.defaultPadding),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: GeneratorTypes.all.map((type) {
                          final isSelected = _selectedGeneratorType == type;
                          return FilterChip(
                            label: Text(GeneratorTypes.getDisplayName(type)),
                            selected: isSelected,
                            onSelected: (selected) {
                              setState(() {
                                _selectedGeneratorType = selected ? type : null;
                                // Clear model selection when changing generator type
                                if (selected) {
                                  _modelNameController.clear();
                                  _selectedModelId = null;
                                }
                              });
                            },
                            selectedColor: theme.colorScheme.primaryContainer,
                          );
                        }).toList(),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: AppConstants.defaultPadding),

              // Model Name Input with Autocomplete
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppConstants.defaultPadding),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l10n.modelName,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: AppConstants.smallPadding),
                      Text(
                        l10n.modelNameDescription,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: AppConstants.defaultPadding),
                      _selectedGeneratorType != null
                          ? _buildModelAutocomplete(theme)
                          : TextField(
                              controller: _modelNameController,
                              enabled: false,
                              decoration: InputDecoration(
                                hintText: 'Select a generator type first',
                                border: const OutlineInputBorder(),
                                prefixIcon: const Icon(Icons.model_training),
                              ),
                            ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: AppConstants.defaultPadding),

              // Ollama Setup Info
              if (_selectedGeneratorType == GeneratorTypes.ollama)
                Card(
                  color: theme.colorScheme.primaryContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(AppConstants.defaultPadding),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.info_outline,
                              color: theme.colorScheme.onPrimaryContainer,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              l10n.ollamaSetup,
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: theme.colorScheme.onPrimaryContainer,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Make sure Ollama is running locally:\n\n'
                          '1. Install Ollama: ollama.ai\n'
                          '2. Pull a model: ollama pull llama2\n'
                          '3. Start server: ollama serve\n'
                          '4. Endpoint: $_ollamaEndpoint',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onPrimaryContainer,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Popular models: llama2, llama3, gemma, mistral, codellama',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onPrimaryContainer,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              if (_selectedGeneratorType == GeneratorTypes.ollama)
                const SizedBox(height: AppConstants.defaultPadding),

              // API Key Input (if needed)
              if (_needsApiKey(_selectedGeneratorType))
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(AppConstants.defaultPadding),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              l10n.apiKey,
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Chip(
                              label: const Text('Optional'),
                              labelStyle: theme.textTheme.labelSmall,
                              visualDensity: VisualDensity.compact,
                            ),
                          ],
                        ),
                        const SizedBox(height: AppConstants.smallPadding),
                        Text(
                          'API key for ${GeneratorTypes.getDisplayName(_selectedGeneratorType!)}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: AppConstants.defaultPadding),
                        TextField(
                          controller: _apiKeyController,
                          obscureText: true,
                          onChanged: (_) {
                            // Reset validation state when key changes
                            if (_apiKeyValid != null) {
                              setState(() {
                                _apiKeyValid = null;
                                _apiKeyValidationMessage = null;
                              });
                            }
                          },
                          decoration: InputDecoration(
                            hintText: 'sk-...',
                            border: const OutlineInputBorder(),
                            prefixIcon: const Icon(Icons.key),
                            suffixIcon: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                // Validation status indicator
                                if (_isValidatingApiKey)
                                  const Padding(
                                    padding: EdgeInsets.all(12),
                                    child: SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(strokeWidth: 2),
                                    ),
                                  )
                                else if (_apiKeyValid == true)
                                  const Padding(
                                    padding: EdgeInsets.all(12),
                                    child: Icon(Icons.check_circle, color: Colors.green),
                                  )
                                else if (_apiKeyValid == false)
                                  const Padding(
                                    padding: EdgeInsets.all(12),
                                    child: Icon(Icons.error, color: Colors.red),
                                  ),
                                // Validate button
                                TextButton(
                                  onPressed: _apiKeyController.text.isEmpty || _isValidatingApiKey
                                      ? null
                                      : _validateApiKey,
                                  child: const Text('Validate'),
                                ),
                                // Info button
                                IconButton(
                                  icon: const Icon(Icons.info_outline),
                                  onPressed: () {
                                    _showApiKeyInfo(context);
                                  },
                                ),
                              ],
                            ),
                          ),
                        ),
                        // Validation message
                        if (_apiKeyValidationMessage != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              _apiKeyValidationMessage!,
                              style: TextStyle(
                                fontSize: 12,
                                color: _apiKeyValid == true ? Colors.green : Colors.red,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              const SizedBox(height: AppConstants.largePadding),

              // Continue Button
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _continueToProbeSelection,
                  icon: const Icon(Icons.arrow_forward),
                  label: Text(l10n.continueToProbeSelection),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _getExampleModelName(String type) {
    switch (type) {
      case GeneratorTypes.ollama:
        return 'llama2';
      case GeneratorTypes.openai:
        return 'gpt-3.5-turbo';
      case GeneratorTypes.huggingface:
        return 'gpt2';
      case GeneratorTypes.anthropic:
        return 'claude-3-opus-20240229';
      case GeneratorTypes.cohere:
        return 'command';
      case GeneratorTypes.replicate:
        return 'meta/llama-2-70b-chat';
      case GeneratorTypes.litellm:
        return 'ollama/llama2';
      case GeneratorTypes.nim:
        return 'meta/llama-3.1-8b-instruct';
      default:
        return '';
    }
  }

  String _getModelHint(BuildContext context, String? type) {
    final l10n = AppLocalizations.of(context)!;
    if (type == null) return 'Select a generator type first';

    switch (type) {
      case GeneratorTypes.openai:
        return l10n.modelHintOpenai;
      case GeneratorTypes.huggingface:
        return l10n.modelHintHuggingface;
      case GeneratorTypes.replicate:
        return l10n.modelHintReplicate;
      case GeneratorTypes.cohere:
        return l10n.modelHintCohere;
      case GeneratorTypes.anthropic:
        return l10n.modelHintAnthropic;
      case GeneratorTypes.litellm:
        return l10n.modelHintLitellm;
      case GeneratorTypes.nim:
        return l10n.modelHintNim;
      case GeneratorTypes.ollama:
        return l10n.modelHintOllama;
      default:
        return 'e.g., ${_getExampleModelName(type)}';
    }
  }

  bool _needsApiKey(String? type) {
    if (type == null) return false;
    // Ollama, HuggingFace, and LiteLLM can run without API keys (local or proxy)
    return [
      GeneratorTypes.openai,
      GeneratorTypes.anthropic,
      GeneratorTypes.cohere,
      GeneratorTypes.replicate,
      GeneratorTypes.groq,
      GeneratorTypes.mistral,
      GeneratorTypes.azure,
      GeneratorTypes.bedrock,
      GeneratorTypes.nim,
    ].contains(type);
  }

  void _showApiKeyInfo(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.apiKeyInformation),
        content: Text(l10n.apiKeyInfoContent),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(l10n.gotIt),
          ),
        ],
      ),
    );
  }

  /// Build autocomplete widget for model selection
  Widget _buildModelAutocomplete(ThemeData theme) {
    final modelsAsync = ref.watch(generatorModelsProvider(_selectedGeneratorType!));

    return modelsAsync.when(
      data: (modelsResponse) {
        final models = modelsResponse.models;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Autocomplete<GeneratorModel>(
              optionsBuilder: (TextEditingValue textEditingValue) {
                if (textEditingValue.text.isEmpty) {
                  return models;
                }
                // If text exactly matches a model ID (auto-populated or just
                // selected), show all models instead of filtering
                if (models.any((m) => m.id == textEditingValue.text)) {
                  return models;
                }
                return models.where((model) {
                  final searchLower = textEditingValue.text.toLowerCase();
                  return model.id.toLowerCase().contains(searchLower) ||
                      model.name.toLowerCase().contains(searchLower) ||
                      model.description.toLowerCase().contains(searchLower);
                });
              },
              displayStringForOption: (GeneratorModel option) => option.id,
              fieldViewBuilder: (
                BuildContext context,
                TextEditingController controller,
                FocusNode focusNode,
                VoidCallback onFieldSubmitted,
              ) {
                // Sync with our controller
                if (_modelNameController.text.isEmpty && controller.text.isEmpty) {
                  // Set initial value to first recommended model if available
                  final recommended = models.where((m) => m.recommended).toList();
                  if (recommended.isNotEmpty && _modelNameController.text.isEmpty) {
                    _modelNameController.text = recommended.first.id;
                    controller.text = recommended.first.id;
                    _selectedModelId = recommended.first.id;
                  }
                }

                return TextField(
                  controller: controller,
                  focusNode: focusNode,
                  decoration: InputDecoration(
                    hintText: 'Type to search or select a model',
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.model_training),
                    suffixIcon: controller.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear),
                            onPressed: () {
                              controller.clear();
                              _modelNameController.clear();
                              _selectedModelId = null;
                            },
                          )
                        : null,
                  ),
                  onChanged: (value) {
                    _modelNameController.text = value;
                    // If user is typing manually, clear the selected model ID
                    _selectedModelId = null;
                  },
                );
              },
              optionsViewBuilder: (
                BuildContext context,
                AutocompleteOnSelected<GeneratorModel> onSelected,
                Iterable<GeneratorModel> options,
              ) {
                return Align(
                  alignment: Alignment.topLeft,
                  child: Material(
                    elevation: 4.0,
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxHeight: 300, maxWidth: 400),
                      child: ListView.builder(
                        padding: EdgeInsets.zero,
                        shrinkWrap: true,
                        itemCount: options.length,
                        itemBuilder: (BuildContext context, int index) {
                          final model = options.elementAt(index);
                          return ListTile(
                            leading: Icon(
                              model.recommended ? Icons.star : Icons.model_training,
                              color: model.recommended
                                  ? theme.colorScheme.primary
                                  : theme.colorScheme.onSurfaceVariant,
                              size: 20,
                            ),
                            title: Text(
                              model.name,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                fontWeight: model.recommended ? FontWeight.bold : FontWeight.normal,
                              ),
                            ),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  model.id,
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    fontFamily: 'monospace',
                                    color: theme.colorScheme.onSurfaceVariant,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  model.description,
                                  style: theme.textTheme.bodySmall,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ],
                            ),
                            trailing: model.contextLength != null
                                ? Chip(
                                    label: Text(
                                      '${model.contextLength}K',
                                      style: theme.textTheme.labelSmall,
                                    ),
                                    visualDensity: VisualDensity.compact,
                                  )
                                : null,
                            isThreeLine: true,
                            onTap: () {
                              onSelected(model);
                            },
                          );
                        },
                      ),
                    ),
                  ),
                );
              },
              onSelected: (GeneratorModel selection) {
                setState(() {
                  _modelNameController.text = selection.id;
                  _selectedModelId = selection.id;
                });
              },
            ),
            const SizedBox(height: 8),
            // Show API key requirement and notes
            if (modelsResponse.requiresApiKey) ...[
              Row(
                children: [
                  Icon(
                    Icons.key,
                    size: 16,
                    color: theme.colorScheme.primary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'API Key Required: ${modelsResponse.apiKeyEnvVar}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.primary,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ],
            if (modelsResponse.note != null) ...[
              const SizedBox(height: 4),
              Text(
                modelsResponse.note!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
            const SizedBox(height: 8),
            // Show recommended models as chips
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: models
                  .where((m) => m.recommended)
                  .map((model) => ActionChip(
                        avatar: const Icon(Icons.star, size: 16),
                        label: Text(model.id),
                        labelStyle: theme.textTheme.labelSmall,
                        visualDensity: VisualDensity.compact,
                        onPressed: () {
                          setState(() {
                            _modelNameController.text = model.id;
                            _selectedModelId = model.id;
                          });
                        },
                      ))
                  .toList(),
            ),
          ],
        );
      },
      loading: () => const Center(
        child: Padding(
          padding: EdgeInsets.all(16.0),
          child: CircularProgressIndicator(),
        ),
      ),
      error: (error, stack) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _modelNameController,
            decoration: InputDecoration(
              hintText: _getModelHint(context, _selectedGeneratorType),
              border: const OutlineInputBorder(),
              prefixIcon: const Icon(Icons.model_training),
              errorText: 'Failed to load models',
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: theme.colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.warning,
                  size: 16,
                  color: theme.colorScheme.onErrorContainer,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Could not load model list. You can still enter a model name manually.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onErrorContainer,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
