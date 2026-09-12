import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_highlight/flutter_highlight.dart';
import 'package:flutter_highlight/themes/monokai-sublime.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../models/custom_probe.dart';
import '../../providers/custom_probe_provider.dart';
import '../../utils/ui_helpers.dart';

class WriteProbeScreen extends ConsumerStatefulWidget {
  final CustomProbeWithCode? existingProbe;

  const WriteProbeScreen({super.key, this.existingProbe});

  @override
  ConsumerState<WriteProbeScreen> createState() => _WriteProbeScreenState();
}

class _WriteProbeScreenState extends ConsumerState<WriteProbeScreen> {
  final TextEditingController _codeController = TextEditingController();
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _descriptionController = TextEditingController();

  ProbeTemplate _selectedTemplate = ProbeTemplate.basic;
  ProbeValidationResult? _validationResult;
  bool _isValidating = false;
  bool _isSaving = false;
  bool _showPreview = false;
  Timer? _debounceTimer;

  @override
  void initState() {
    super.initState();
    if (widget.existingProbe != null) {
      // Load existing probe data
      _nameController.text = widget.existingProbe!.probe.name;
      _descriptionController.text = widget.existingProbe!.probe.description ?? '';
      _codeController.text = widget.existingProbe!.code;
      _validateCode();
    } else {
      // Load default template for new probe
      _loadTemplate(ProbeTemplate.basic);
    }
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _codeController.dispose();
    _nameController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _loadTemplate(ProbeTemplate template) async {
    setState(() {
      _selectedTemplate = template;
    });

    try {
      final service = ref.read(customProbeServiceProvider);
      final templateCode = await service.getTemplate(template);
      setState(() {
        _codeController.text = templateCode;
      });
      _validateCode();
    } catch (e) {
      if (mounted) {
        context.showError('Failed to load template: $e');
      }
    }
  }

  Future<void> _validateCode() async {
    if (_codeController.text.isEmpty) {
      setState(() {
        _validationResult = null;
      });
      return;
    }

    setState(() {
      _isValidating = true;
    });

    try {
      final service = ref.read(customProbeServiceProvider);
      final result = await service.validateCode(_codeController.text);
      setState(() {
        _validationResult = result;
      });
    } catch (e) {
      if (mounted) {
        context.showError('Validation failed: $e');
      }
    } finally {
      setState(() {
        _isValidating = false;
      });
    }
  }

  void _handleTabKey() {
    final currentSelection = _codeController.selection;
    final text = _codeController.text;

    // Insert 4 spaces at cursor position
    final newText = text.replaceRange(
      currentSelection.start,
      currentSelection.end,
      '    ',
    );

    _codeController.value = TextEditingValue(
      text: newText,
      selection: TextSelection.collapsed(
        offset: currentSelection.start + 4,
      ),
    );
  }

  void _handleEnterKey() {
    final currentSelection = _codeController.selection;
    final text = _codeController.text;

    // Find the start of the current line
    final beforeCursor = text.substring(0, currentSelection.start);
    final lastNewline = beforeCursor.lastIndexOf('\n');
    final currentLineStart = lastNewline + 1;
    final currentLine = text.substring(currentLineStart, currentSelection.start);

    // Count leading spaces on current line
    final leadingSpaces = RegExp(r'^\s*').firstMatch(currentLine)?.group(0) ?? '';

    // Insert newline with same indentation
    final newText = text.replaceRange(
      currentSelection.start,
      currentSelection.end,
      '\n$leadingSpaces',
    );

    _codeController.value = TextEditingValue(
      text: newText,
      selection: TextSelection.collapsed(
        offset: currentSelection.start + 1 + leadingSpaces.length,
      ),
    );
  }

  Future<void> _saveProbe() async {
    final l10n = AppLocalizations.of(context)!;

    if (_nameController.text.isEmpty) {
      context.showError(l10n.enterProbeName);
      return;
    }

    if (_codeController.text.isEmpty) {
      context.showError(l10n.enterProbeCode);
      return;
    }

    // Validate first
    if (_validationResult == null || !_validationResult!.valid) {
      context.showError(l10n.fixValidationErrors);
      return;
    }

    setState(() {
      _isSaving = true;
    });

    try {
      final service = ref.read(customProbeServiceProvider);
      final isEditing = widget.existingProbe != null;

      if (isEditing) {
        // Update existing probe
        await service.updateProbe(
          name: _nameController.text,
          code: _codeController.text,
          description: _descriptionController.text.isEmpty ? null : _descriptionController.text,
        );
      } else {
        // Create new probe
        await service.createProbe(
          name: _nameController.text,
          code: _codeController.text,
          description: _descriptionController.text.isEmpty ? null : _descriptionController.text,
        );
      }

      if (mounted) {
        context.showInfo(isEditing ? 'Probe updated successfully!' : l10n.probeCreatedSuccess);
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        context.showError('Failed to save probe: $e');
      }
    } finally {
      setState(() {
        _isSaving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.existingProbe != null ? 'Edit Custom Probe' : 'Write Custom Probe'),
        actions: [
          IconButton(
            icon: Icon(_showPreview ? Icons.code : Icons.visibility),
            onPressed: () {
              setState(() {
                _showPreview = !_showPreview;
              });
            },
            tooltip: _showPreview ? 'Show Editor' : 'Show Preview',
          ),
          if (_validationResult != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Chip(
                label: Text(
                  _validationResult!.valid ? 'Valid' : 'Invalid',
                  style: TextStyle(
                    color: _validationResult!.valid ? Colors.green : Colors.red,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                backgroundColor: theme.colorScheme.surface,
              ),
            ),
        ],
      ),
      body: Row(
        children: [
          // Main editor area
          Expanded(
            flex: 2,
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppConstants.defaultPadding),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Template Selection
                  _buildTemplateSelector(theme),
                  const SizedBox(height: AppConstants.largePadding),

                  // Probe Details
                  _buildProbeDetails(theme),
                  const SizedBox(height: AppConstants.largePadding),

                  // Code Editor or Preview
                  _showPreview ? _buildPreview(theme) : _buildCodeEditor(theme),
                  const SizedBox(height: AppConstants.largePadding),

                  // Actions
                  _buildActions(theme),
                ],
              ),
            ),
          ),

          // Validation sidebar
          if (!_showPreview && _validationResult != null)
            Container(
              width: 300,
              decoration: BoxDecoration(
                border: Border(
                  left: BorderSide(
                    color: theme.colorScheme.outline.withValues(alpha: 0.2),
                  ),
                ),
              ),
              child: _buildValidationPanel(theme),
            ),
        ],
      ),
    );
  }

  Widget _buildTemplateSelector(ThemeData theme) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.library_books, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Start with Template',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppConstants.defaultPadding),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: ProbeTemplate.values.map((template) {
                final isSelected = _selectedTemplate == template;
                return FilterChip(
                  label: Text(template.displayName),
                  selected: isSelected,
                  onSelected: (_) => _loadTemplate(template),
                  selectedColor: theme.colorScheme.primaryContainer,
                );
              }).toList(),
            ),
            if (_selectedTemplate != null) ...[
              const SizedBox(height: 8),
              Text(
                _selectedTemplate.description,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildProbeDetails(ThemeData theme) {
    final l10n = AppLocalizations.of(context)!;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Probe Details',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: AppConstants.defaultPadding),
            TextField(
              controller: _nameController,
              decoration: InputDecoration(
                labelText: l10n.probeName,
                hintText: 'MyCustomProbe',
                border: const OutlineInputBorder(),
                helperText: 'Must be a valid Python class name',
              ),
            ),
            const SizedBox(height: AppConstants.defaultPadding),
            TextField(
              controller: _descriptionController,
              maxLines: 2,
              decoration: InputDecoration(
                labelText: l10n.descriptionOptional,
                hintText: 'A brief description of what this probe tests for',
                border: const OutlineInputBorder(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCodeEditor(ThemeData theme) {
    final l10n = AppLocalizations.of(context)!;

    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppConstants.defaultPadding),
            child: Row(
              children: [
                Text(
                  'Python Code',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const Spacer(),
                if (_isValidating)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  TextButton.icon(
                    onPressed: _validateCode,
                    icon: const Icon(Icons.check_circle),
                    label: Text(l10n.validate),
                  ),
              ],
            ),
          ),
          const Divider(height: 1),
          Container(
            height: 400,
            padding: const EdgeInsets.all(AppConstants.defaultPadding),
            child: Shortcuts(
              shortcuts: {
                LogicalKeySet(LogicalKeyboardKey.tab): const _InsertTabIntent(),
                LogicalKeySet(LogicalKeyboardKey.enter): const _InsertNewlineIntent(),
              },
              child: Actions(
                actions: {
                  _InsertTabIntent: CallbackAction<_InsertTabIntent>(
                    onInvoke: (_) {
                      _handleTabKey();
                      return null;
                    },
                  ),
                  _InsertNewlineIntent: CallbackAction<_InsertNewlineIntent>(
                    onInvoke: (_) {
                      _handleEnterKey();
                      return null;
                    },
                  ),
                },
                child: TextField(
                  controller: _codeController,
                  maxLines: null,
                  expands: true,
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 14,
                  ),
                  decoration: InputDecoration(
                    border: InputBorder.none,
                    hintText: l10n.probeCodeHint,
                  ),
                  onChanged: (_) {
                    // Cancel the previous timer
                    _debounceTimer?.cancel();
                    // Create a new timer for debounced validation
                    _debounceTimer = Timer(const Duration(seconds: 1), () {
                      if (mounted) _validateCode();
                    });
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPreview(ThemeData theme) {
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppConstants.defaultPadding),
            child: Text(
              'Code Preview (Syntax Highlighted)',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const Divider(height: 1),
          Container(
            constraints: const BoxConstraints(
              maxHeight: 600,
              minWidth: double.infinity,
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(
                horizontal: AppConstants.defaultPadding * 2,
                vertical: AppConstants.defaultPadding,
              ),
              child: SizedBox(
                width: double.infinity,
                child: HighlightView(
                  _codeController.text.isEmpty
                      ? '# No code yet...'
                      : _codeController.text,
                  language: 'python',
                  theme: monokaiSublimeTheme,
                  padding: const EdgeInsets.all(20),
                  textStyle: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 14,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildValidationPanel(ThemeData theme) {
    final result = _validationResult!;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppConstants.defaultPadding),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Validation Results',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: AppConstants.defaultPadding),

          // Status
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: result.valid
                  ? Colors.green.withValues(alpha: 0.1)
                  : Colors.red.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Icon(
                  result.valid ? Icons.check_circle : Icons.error,
                  color: result.valid ? Colors.green : Colors.red,
                ),
                const SizedBox(width: 8),
                Text(
                  result.valid ? 'Code is valid' : 'Has errors',
                  style: TextStyle(
                    color: result.valid ? Colors.green : Colors.red,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),

          // Errors
          if (result.errors.isNotEmpty) ...[
            const SizedBox(height: AppConstants.defaultPadding),
            Text(
              'Errors',
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.red,
              ),
            ),
            const SizedBox(height: 8),
            ...result.errors.map((error) => _buildErrorItem(error, theme)),
          ],

          // Warnings
          if (result.warnings.isNotEmpty) ...[
            const SizedBox(height: AppConstants.defaultPadding),
            Text(
              'Warnings',
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.orange,
              ),
            ),
            const SizedBox(height: 8),
            ...result.warnings.map((warning) => _buildWarningItem(warning, theme)),
          ],

          // Probe Info
          if (result.probeInfo != null) ...[
            const SizedBox(height: AppConstants.defaultPadding),
            Text(
              'Detected Features',
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            _buildProbeInfoPanel(result.probeInfo!, theme),
          ],
        ],
      ),
    );
  }

  Widget _buildErrorItem(ValidationError error, ThemeData theme) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.red.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (error.line != null)
            Text(
              'Line ${error.line}${error.column != null ? ':${error.column}' : ''}',
              style: theme.textTheme.labelSmall?.copyWith(
                color: Colors.red,
                fontWeight: FontWeight.bold,
              ),
            ),
          Text(
            error.message,
            style: theme.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Widget _buildWarningItem(String warning, ThemeData theme) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.orange.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: Colors.orange.withValues(alpha: 0.2)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning, size: 16, color: Colors.orange),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              warning,
              style: theme.textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProbeInfoPanel(Map<String, dynamic> info, ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (info['has_prompts'] == true)
          _buildFeatureChip('Has prompts', Icons.chat, theme),
        if (info['has_goal'] == true)
          _buildFeatureChip('Has goal', Icons.flag, theme),
        if (info['has_primary_detector'] == true)
          _buildFeatureChip('Has detector', Icons.sensors, theme),
        if (info['has_tags'] == true)
          _buildFeatureChip('Has tags', Icons.label, theme),
      ],
    );
  }

  Widget _buildFeatureChip(String label, IconData icon, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Chip(
        label: Text(label),
        avatar: Icon(icon, size: 16),
        visualDensity: VisualDensity.compact,
      ),
    );
  }

  Widget _buildActions(ThemeData theme) {
    final l10n = AppLocalizations.of(context)!;

    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.cancel),
            label: Text(l10n.cancel),
          ),
        ),
        const SizedBox(width: AppConstants.defaultPadding),
        Expanded(
          flex: 2,
          child: FilledButton.icon(
            onPressed: _isSaving ? null : _saveProbe,
            icon: _isSaving
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.save),
            label: Text(_isSaving ? 'Saving...' : (widget.existingProbe != null ? 'Update Probe' : 'Save Probe')),
          ),
        ),
      ],
    );
  }
}

// Intent classes for custom keyboard shortcuts
class _InsertTabIntent extends Intent {
  const _InsertTabIntent();
}

class _InsertNewlineIntent extends Intent {
  const _InsertNewlineIntent();
}
