import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../providers/scan_provider.dart';
import '../../providers/scan_config_provider.dart';
import '../../providers/background_scans_provider.dart';
import '../../services/background_scan_service.dart';
import '../../models/scan_status.dart';
import '../../models/scan_config.dart';
import '../results/enhanced_results_screen.dart';
import '../background_tasks/background_tasks_screen.dart';

class ScanExecutionScreen extends ConsumerStatefulWidget {
  const ScanExecutionScreen({super.key});

  @override
  ConsumerState<ScanExecutionScreen> createState() => _ScanExecutionScreenState();
}

class _ScanExecutionScreenState extends ConsumerState<ScanExecutionScreen> {
  final ScrollController _logScrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    // Start the scan when screen loads
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _startScan();
    });
  }

  @override
  void dispose() {
    _logScrollController.dispose();
    // Note: Don't call ref.read() here - the provider's own dispose handles cleanup
    super.dispose();
  }

  Future<void> _startScan() async {
    await ref.read(activeScanProvider.notifier).startScan();

    final scanState = ref.read(activeScanProvider);
    if (scanState.scanId != null) {
      // Connect via WebSocket for real-time updates
      ref.read(activeScanProvider.notifier).connectWebSocket(scanState.scanId!);
    }
  }

  Future<void> _cancelScan() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(AppLocalizations.of(dialogContext)!.cancelScan),
        content: Text(AppLocalizations.of(dialogContext)!.cancelScanConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text(AppLocalizations.of(dialogContext)!.no),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(AppLocalizations.of(dialogContext)!.yesCancelScan),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      ref.read(activeScanProvider.notifier).disconnectWebSocket();
      await ref.read(activeScanProvider.notifier).cancelScan();

      if (mounted) {
        Navigator.pop(context);
      }
    }
  }

  Future<void> _moveToBackground() async {
    // Move current scan to background
    ref.read(backgroundScanActionsProvider).moveCurrentScanToBackground();

    if (mounted) {
      Navigator.pop(context);
    }
  }

  Future<String?> _showBackgroundDialog() async {
    return showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: Row(
          children: [
            const Icon(Icons.info_outline, size: 28),
            const SizedBox(width: 12),
            Text(AppLocalizations.of(dialogContext)!.scanInProgress),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Your scan is still running. What would you like to do?',
              style: Theme.of(dialogContext).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            _buildDialogOption(
              context: dialogContext,
              icon: Icons.visibility,
              title: 'Stay on Screen',
              subtitle: 'Continue watching scan progress',
            ),
            const SizedBox(height: 8),
            _buildDialogOption(
              context: dialogContext,
              icon: Icons.arrow_circle_down,
              title: 'Run in Background',
              subtitle: 'Navigate away, scan continues running',
              recommended: true,
            ),
            const SizedBox(height: 8),
            _buildDialogOption(
              context: dialogContext,
              icon: Icons.cancel,
              title: 'Cancel Scan',
              subtitle: 'Stop the scan immediately',
              isDestructive: true,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, 'stay'),
            child: const Text('Stay'),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.pop(dialogContext, 'background'),
            icon: const Icon(Icons.arrow_circle_down),
            label: const Text('Background'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, 'cancel'),
            style: TextButton.styleFrom(
              foregroundColor: Theme.of(dialogContext).colorScheme.error,
            ),
            child: const Text('Cancel Scan'),
          ),
        ],
      ),
    );
  }

  Widget _buildDialogOption({
    required BuildContext context,
    required IconData icon,
    required String title,
    required String subtitle,
    bool recommended = false,
    bool isDestructive = false,
  }) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: recommended
            ? theme.colorScheme.primaryContainer.withValues(alpha: 0.3)
            : isDestructive
                ? theme.colorScheme.errorContainer.withValues(alpha: 0.2)
                : theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
        border: recommended
            ? Border.all(color: theme.colorScheme.primary, width: 2)
            : null,
      ),
      child: Row(
        children: [
          Icon(
            icon,
            color: recommended
                ? theme.colorScheme.primary
                : isDestructive
                    ? theme.colorScheme.error
                    : theme.colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: isDestructive ? theme.colorScheme.error : null,
                      ),
                    ),
                    if (recommended) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primary,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          'RECOMMENDED',
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.onPrimary,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _viewResults() {
    final scanState = ref.read(activeScanProvider);
    if (scanState.scanId != null) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (context) => EnhancedResultsScreen(
            scanId: scanState.scanId!,
            scanStatus: scanState.status,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scanState = ref.watch(activeScanProvider);
    final config = ref.watch(scanConfigProvider);

    return PopScope(
      canPop: !(scanState.status?.status.isActive ?? false),
      onPopInvokedWithResult: (bool didPop, dynamic result) async {
        if (didPop) {
          // Scan is not active, safe to leave
          // Disconnect WebSocket if still connected
          ref.read(activeScanProvider.notifier).disconnectWebSocket();
          return;
        }

        // If we reach here, the pop was blocked (scan is active)
        // Show 3-option dialog
        final choice = await _showBackgroundDialog();

        if (choice == 'background' && mounted) {
          await _moveToBackground();
        } else if (choice == 'cancel' && mounted) {
          ref.read(activeScanProvider.notifier).disconnectWebSocket();
          await ref.read(activeScanProvider.notifier).cancelScan();
          if (mounted) {
            Navigator.pop(context);
          }
        }
        // If 'stay', do nothing (stay on screen)
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(AppLocalizations.of(context)!.scanExecution),
          actions: [
            if (scanState.status?.status.isActive ?? false)
              IconButton(
                icon: const Icon(Icons.stop),
                onPressed: _cancelScan,
                tooltip: AppLocalizations.of(context)!.cancelScan,
              ),
          ],
        ),
        body: scanState.isLoading && scanState.scanId == null
            ? Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 16),
                    Text(AppLocalizations.of(context)!.startingScan),
                  ],
                ),
              )
            : scanState.error != null
                ? Center(
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
                          'Error Starting Scan',
                          style: theme.textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 32),
                          child: Text(
                            scanState.error!,
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodyMedium,
                          ),
                        ),
                        const SizedBox(height: 24),
                        FilledButton.icon(
                          onPressed: () => Navigator.pop(context),
                          icon: const Icon(Icons.arrow_back),
                          label: Text(AppLocalizations.of(context)!.goBack),
                        ),
                      ],
                    ),
                  )
                : SingleChildScrollView(
                    padding: const EdgeInsets.all(AppConstants.defaultPadding),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Scan Configuration Card
                        _buildConfigCard(theme, config),
                        const SizedBox(height: AppConstants.defaultPadding),

                        // Progress Card
                        if (scanState.status != null)
                          _buildProgressCard(theme, scanState.status!),
                        const SizedBox(height: AppConstants.defaultPadding),

                        // Status Card
                        if (scanState.status != null)
                          _buildStatusCard(theme, scanState.status!),

                        // Cancel Button (shown when scan is active)
                        if (scanState.status?.status.isActive ?? false) ...[
                          const SizedBox(height: AppConstants.defaultPadding),
                          SizedBox(
                            width: double.infinity,
                            child: OutlinedButton.icon(
                              onPressed: _cancelScan,
                              icon: const Icon(Icons.stop_circle_outlined),
                              label: Text(AppLocalizations.of(context)!.cancelScan),
                              style: OutlinedButton.styleFrom(
                                foregroundColor: theme.colorScheme.error,
                                side: BorderSide(color: theme.colorScheme.error),
                                padding: const EdgeInsets.symmetric(vertical: 16),
                              ),
                            ),
                          ),
                        ],

                        // Results Button
                        if (scanState.status?.status.isFinished ?? false) ...[
                          const SizedBox(height: AppConstants.defaultPadding),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton.icon(
                              onPressed: _viewResults,
                              icon: const Icon(Icons.assessment),
                              label: Text(AppLocalizations.of(context)!.viewResults),
                            ),
                          ),
                        ],

                        // Other Running Scans Section
                        _buildOtherRunningScans(theme, scanState.scanId),
                      ],
                    ),
                  ),
      ),
    );
  }

  Widget _buildConfigCard(ThemeData theme, ScanConfig? config) {
    if (config == null) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Scan Configuration',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: AppConstants.defaultPadding),
            _buildInfoRow(Icons.model_training, 'Model',
                '${GeneratorTypes.getDisplayName(config.targetType)} - ${config.targetName}'),
            const SizedBox(height: 8),
            _buildInfoRow(Icons.science, 'Probes',
                config.probes.join(', ')),
            const SizedBox(height: 8),
            _buildInfoRow(Icons.auto_awesome, 'Generations',
                config.generations.toString()),
            const SizedBox(height: 8),
            _buildInfoRow(Icons.speed, 'Threshold',
                config.evalThreshold.toString()),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressCard(ThemeData theme, ScanStatusInfo status) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Progress',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  '${status.progress.toStringAsFixed(1)}%',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: theme.colorScheme.primary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppConstants.defaultPadding),
            LinearProgressIndicator(
              value: status.progress / 100,
              minHeight: 8,
              borderRadius: BorderRadius.circular(4),
            ),
            if (status.currentProbe != null) ...[
              const SizedBox(height: AppConstants.defaultPadding),
              Text(
                'Current: ${status.currentProbe}',
                style: theme.textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
            // Show time info (elapsed and ETA)
            if (status.elapsedTime != null || status.estimatedRemaining != null) ...[
              const SizedBox(height: 12),
              _buildTimeInfoRow(theme, status),
            ],
            // Show iteration info if available
            if (status.totalIterations > 0) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(
                    Icons.repeat,
                    size: 16,
                    color: theme.colorScheme.secondary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'Iteration: ${status.currentIteration}/${status.totalIterations}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.secondary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildTimeInfoRow(ThemeData theme, ScanStatusInfo status) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          // Elapsed Time
          if (status.elapsedTime != null) ...[
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.timer_outlined,
                  size: 18,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 6),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Elapsed',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    Text(
                      status.elapsedTime!,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: theme.colorScheme.primary,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
          // Divider between elapsed and ETA
          if (status.elapsedTime != null && status.estimatedRemaining != null)
            Container(
              height: 30,
              width: 1,
              color: theme.colorScheme.outlineVariant,
            ),
          // Estimated Remaining (ETA)
          if (status.estimatedRemaining != null) ...[
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.hourglass_bottom,
                  size: 18,
                  color: theme.colorScheme.secondary,
                ),
                const SizedBox(width: 6),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Remaining',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    Text(
                      status.estimatedRemaining!,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: theme.colorScheme.secondary,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatusCard(ThemeData theme, ScanStatusInfo status) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                // Animated icon for running status
                if (status.status == ScanStatus.running)
                  SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        _getStatusColor(theme, status.status),
                      ),
                    ),
                  )
                else
                  Icon(
                    _getStatusIcon(status.status),
                    color: _getStatusColor(theme, status.status),
                  ),
                const SizedBox(width: 8),
                Text(
                  'Status: ${status.status.displayName}',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            // Show error message if status is failed and error message exists
            if (status.status == ScanStatus.failed && status.errorMessage != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: theme.colorScheme.error.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: theme.colorScheme.error.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.error_outline,
                      color: theme.colorScheme.error,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        status.errorMessage!,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.error,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: AppConstants.defaultPadding),
            Row(
              children: [
                Expanded(
                  flex: 3,
                  child: _buildResultCard(
                    theme,
                    status,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: _buildStatCard(
                    theme,
                    'Probes',
                    '${status.totalProbes}',
                    Icons.science,
                    theme.colorScheme.primary,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard(ThemeData theme, ScanStatusInfo status) {
    final int total = status.passed + status.failed;
    final bool isRunning = status.status == ScanStatus.running;

    // If scan is still running and no results yet, show progress
    if (isRunning && total == 0) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: theme.colorScheme.primary.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: theme.colorScheme.primary.withValues(alpha: 0.3),
            width: 2,
          ),
        ),
        child: Column(
          children: [
            Icon(Icons.pending, color: theme.colorScheme.primary, size: 24),
            const SizedBox(height: 4),
            Text(
              'Running',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: theme.colorScheme.primary,
              ),
            ),
            Text(
              '${status.currentIteration}/${status.totalIterations}',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: theme.colorScheme.primary,
              ),
            ),
            Text(
              'Iteration',
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
      );
    }

    // Show results
    final bool isPassing = total == 0 || status.failed == 0;
    final Color color = isPassing ? Colors.green : Colors.red;
    final IconData icon = isPassing ? Icons.check_circle : Icons.error;
    final String statusText = isPassing ? 'PASS' : 'FAIL';
    final String resultText = total > 0 ? '${status.passed}/$total' : '0/0';

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: color.withValues(alpha: 0.3),
          width: 2,
        ),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 4),
          Text(
            statusText,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          Text(
            resultText,
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          Text(
            'Tests',
            style: theme.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(
    ThemeData theme,
    String label,
    String value,
    IconData icon,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 4),
          Text(
            value,
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          Text(
            label,
            style: theme.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 20),
        const SizedBox(width: 8),
        Text('$label: ', style: const TextStyle(fontWeight: FontWeight.bold)),
        Expanded(
          child: Text(
            value,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }

  IconData _getStatusIcon(ScanStatus status) {
    switch (status) {
      case ScanStatus.pending:
        return Icons.pending;
      case ScanStatus.running:
        return Icons.play_circle;
      case ScanStatus.completed:
        return Icons.check_circle;
      case ScanStatus.failed:
        return Icons.error;
      case ScanStatus.cancelled:
        return Icons.cancel;
    }
  }

  Color _getStatusColor(ThemeData theme, ScanStatus status) {
    switch (status) {
      case ScanStatus.pending:
        return Colors.orange;
      case ScanStatus.running:
        return theme.colorScheme.primary;
      case ScanStatus.completed:
        return Colors.green;
      case ScanStatus.failed:
        return Colors.red;
      case ScanStatus.cancelled:
        return Colors.grey;
    }
  }

  Widget _buildOtherRunningScans(ThemeData theme, String? currentScanId) {
    final backgroundScansAsync = ref.watch(backgroundScansProvider);

    return backgroundScansAsync.when(
      data: (scans) {
        // Filter out the current scan and only show running scans
        final otherScans = scans
            .where((scan) =>
                scan.scanId != currentScanId &&
                scan.isActive)
            .toList();

        if (otherScans.isEmpty) {
          return const SizedBox.shrink();
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 24),
            const Divider(),
            const SizedBox(height: 16),
            Row(
              children: [
                Icon(
                  Icons.alt_route,
                  size: 20,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  'Other Running Scans (${otherScans.length})',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'These scans are running in the background',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            ...otherScans.map((scan) => _buildCompactScanCard(theme, scan)),
          ],
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }

  Widget _buildCompactScanCard(ThemeData theme, BackgroundScan scan) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () {
          // Navigate to background tasks screen
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => const BackgroundTasksScreen(),
            ),
          );
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Icon(
                      Icons.sync,
                      color: theme.colorScheme.primary,
                      size: 16,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          scan.displayName,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          '${scan.config.targetType} • ${scan.config.targetName}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  Icon(
                    Icons.chevron_right,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: (scan.progress ?? 0.0) / 100,  // Convert percentage (0-100) to fraction (0-1)
                  minHeight: 6,
                  backgroundColor: theme.colorScheme.surfaceContainerHighest,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    theme.colorScheme.primary,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    scan.progress != null
                        ? '${scan.progress!.toStringAsFixed(1)}% complete'
                        : 'Starting...',
                    style: theme.textTheme.bodySmall,
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Show ETA if available
                      if (scan.status?.estimatedRemaining != null) ...[
                        Icon(
                          Icons.hourglass_bottom,
                          size: 12,
                          color: theme.colorScheme.secondary,
                        ),
                        const SizedBox(width: 2),
                        Text(
                          scan.status!.estimatedRemaining!,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.secondary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(width: 8),
                      ],
                      // Show elapsed time
                      Icon(
                        Icons.timer_outlined,
                        size: 12,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                      const SizedBox(width: 2),
                      Text(
                        scan.status?.elapsedTime ?? _formatElapsedTime(scan.startTime),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatElapsedTime(DateTime startTime) {
    final elapsed = DateTime.now().difference(startTime);
    if (elapsed.inHours > 0) {
      return '${elapsed.inHours}h ${elapsed.inMinutes % 60}m';
    } else if (elapsed.inMinutes > 0) {
      return '${elapsed.inMinutes}m';
    } else {
      return '${elapsed.inSeconds}s';
    }
  }
}
