import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../models/custom_probe.dart';
import '../../providers/custom_probe_provider.dart';
import '../../utils/ui_helpers.dart';
import '../../widgets/empty_state_widget.dart';
import 'write_probe_screen.dart';

class ManageProbesScreen extends ConsumerStatefulWidget {
  const ManageProbesScreen({super.key});

  @override
  ConsumerState<ManageProbesScreen> createState() => _ManageProbesScreenState();
}

class _ManageProbesScreenState extends ConsumerState<ManageProbesScreen> {
  List<CustomProbe>? _probes;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadProbes();
  }

  Future<void> _loadProbes() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final service = ref.read(customProbeServiceProvider);
      final probes = await service.listProbes();
      setState(() {
        _probes = probes;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _deleteProbe(CustomProbe probe) async {
    final l10n = AppLocalizations.of(context)!;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.deleteProbe),
        content: Text(l10n.deleteProbeConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: Colors.red,
            ),
            child: Text(l10n.delete),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final service = ref.read(customProbeServiceProvider);
        await service.deleteProbe(probe.name);
        if (mounted) {
          context.showInfo('Probe deleted successfully');
          _loadProbes();
        }
      } catch (e) {
        if (mounted) {
          context.showError('Failed to delete probe: $e');
        }
      }
    }
  }

  Future<void> _editProbe(CustomProbe probe) async {
    try {
      final service = ref.read(customProbeServiceProvider);
      final probeWithCode = await service.getProbe(probe.name);

      if (mounted) {
        await Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => WriteProbeScreen(
              existingProbe: probeWithCode,
            ),
          ),
        );
        // Reload probes after returning from edit
        _loadProbes();
      }
    } catch (e) {
      if (mounted) {
        context.showError('Failed to load probe: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.myCustomProbes),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadProbes,
            tooltip: l10n.refresh,
          ),
        ],
      ),
      body: _buildBody(theme),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => const WriteProbeScreen(),
            ),
          );
          _loadProbes();
        },
        icon: const Icon(Icons.add),
        label: Text(l10n.newProbe),
      ),
    );
  }

  Widget _buildBody(ThemeData theme) {
    final l10n = AppLocalizations.of(context)!;

    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: theme.colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              l10n.failedToLoadProbes,
              style: theme.textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              _error!,
              style: theme.textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _loadProbes,
              icon: const Icon(Icons.refresh),
              label: Text(l10n.retry),
            ),
          ],
        ),
      );
    }

    if (_probes == null || _probes!.isEmpty) {
      return EmptyStateWidget(
        type: EmptyStateType.noProbes,
        title: 'No Custom Probes Yet',
        message: 'Create your first custom probe to get started',
        action: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (context) => const WriteProbeScreen()),
          ).then((_) => _loadProbes());
        },
        actionLabel: l10n.newProbe,
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(AppConstants.defaultPadding),
      itemCount: _probes!.length,
      itemBuilder: (context, index) {
        final probe = _probes![index];
        return _buildProbeCard(probe, theme);
      },
    );
  }

  Widget _buildProbeCard(CustomProbe probe, ThemeData theme) {
    return Card(
      margin: const EdgeInsets.only(bottom: AppConstants.defaultPadding),
      child: InkWell(
        onTap: () => _editProbe(probe),
        borderRadius: BorderRadius.circular(AppConstants.borderRadius),
        child: Padding(
          padding: const EdgeInsets.all(AppConstants.defaultPadding),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.code,
                    color: theme.colorScheme.primary,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      probe.name,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.edit),
                    onPressed: () => _editProbe(probe),
                    tooltip: 'Edit',
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete),
                    color: theme.colorScheme.error,
                    onPressed: () => _deleteProbe(probe),
                    tooltip: 'Delete',
                  ),
                ],
              ),
              if (probe.description != null) ...[
                const SizedBox(height: 8),
                Text(
                  probe.description!,
                  style: theme.textTheme.bodyMedium,
                ),
              ],
              if (probe.goal != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(
                      Icons.flag,
                      size: 16,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        probe.goal!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: [
                  if (probe.primaryDetector != null)
                    Chip(
                      label: Text(probe.primaryDetector!),
                      avatar: const Icon(Icons.sensors, size: 16),
                      visualDensity: VisualDensity.compact,
                    ),
                  if (probe.tags != null)
                    ...probe.tags!.map(
                      (tag) => Chip(
                        label: Text(tag),
                        visualDensity: VisualDensity.compact,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(
                    Icons.access_time,
                    size: 14,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'Updated: ${_formatDate(probe.updatedAt)}',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(String isoDate) {
    try {
      final date = DateTime.parse(isoDate);
      final now = DateTime.now();
      final difference = now.difference(date);

      if (difference.inDays == 0) {
        return 'Today';
      } else if (difference.inDays == 1) {
        return 'Yesterday';
      } else if (difference.inDays < 7) {
        return '${difference.inDays} days ago';
      } else {
        return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
      }
    } catch (e) {
      return isoDate;
    }
  }
}
