import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../models/scan_status.dart';

class ResultsScreen extends ConsumerWidget {
  final String scanId;
  final ScanStatusInfo? scanStatus;

  const ResultsScreen({
    super.key,
    required this.scanId,
    this.scanStatus,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context)!.scanResults),
        actions: [
          IconButton(
            icon: const Icon(Icons.share),
            onPressed: () {
              // TODO: Implement share
            },
          ),
          IconButton(
            icon: const Icon(Icons.download),
            onPressed: () {
              // TODO: Implement download report
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(AppConstants.largePadding),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          _getStatusIcon(scanStatus?.status),
                          size: 32,
                          color: _getStatusColor(theme, scanStatus?.status),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Scan ${scanStatus?.status.displayName ?? "Complete"}',
                                style: theme.textTheme.headlineSmall?.copyWith(
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Text(
                                'ID: $scanId',
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppConstants.defaultPadding),

            // Summary Statistics
            if (scanStatus != null) ...[
              Text(
                AppLocalizations.of(context)!.summary,
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: AppConstants.defaultPadding),
              Row(
                children: [
                  Expanded(
                    child: _buildStatCard(
                      theme,
                      AppLocalizations.of(context)!.totalTests,
                      (scanStatus!.passed + scanStatus!.failed).toString(),
                      Icons.science,
                      theme.colorScheme.primary,
                    ),
                  ),
                  const SizedBox(width: AppConstants.defaultPadding),
                  Expanded(
                    child: _buildStatCard(
                      theme,
                      AppLocalizations.of(context)!.passed,
                      scanStatus!.passed.toString(),
                      Icons.check_circle,
                      Colors.green,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppConstants.defaultPadding),
              Row(
                children: [
                  Expanded(
                    child: _buildStatCard(
                      theme,
                      AppLocalizations.of(context)!.failed,
                      scanStatus!.failed.toString(),
                      Icons.error,
                      Colors.red,
                    ),
                  ),
                  const SizedBox(width: AppConstants.defaultPadding),
                  Expanded(
                    child: _buildStatCard(
                      theme,
                      AppLocalizations.of(context)!.passRate,
                      _calculatePassRate(scanStatus!),
                      Icons.percent,
                      theme.colorScheme.secondary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppConstants.largePadding),
            ],

            // Probes Summary
            Text(
              'Probes Executed',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: AppConstants.defaultPadding),
            if (scanStatus != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppConstants.defaultPadding),
                  child: Column(
                    children: [
                      _buildInfoRow(
                        'Total Probes',
                        scanStatus!.totalProbes.toString(),
                        Icons.list,
                      ),
                      const Divider(),
                      _buildInfoRow(
                        'Completed',
                        scanStatus!.completedProbes.toString(),
                        Icons.check,
                      ),
                      if (scanStatus!.currentProbe != null) ...[
                        const Divider(),
                        _buildInfoRow(
                          'Last Probe',
                          scanStatus!.currentProbe!,
                          Icons.science,
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            const SizedBox(height: AppConstants.largePadding),

            // Error Message
            if (scanStatus?.errorMessage != null) ...[
              Card(
                color: theme.colorScheme.errorContainer,
                child: Padding(
                  padding: const EdgeInsets.all(AppConstants.defaultPadding),
                  child: Row(
                    children: [
                      Icon(
                        Icons.error_outline,
                        color: theme.colorScheme.onErrorContainer,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Error',
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: theme.colorScheme.onErrorContainer,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              scanStatus!.errorMessage!,
                              style: TextStyle(
                                color: theme.colorScheme.onErrorContainer,
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
            ],

            // Actions
            Text(
              'Actions',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: AppConstants.defaultPadding),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () {
                  // TODO: Export report
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Export feature coming soon'),
                    ),
                  );
                },
                icon: const Icon(Icons.file_download),
                label: const Text('Export Full Report'),
              ),
            ),
            const SizedBox(height: AppConstants.smallPadding),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  Navigator.popUntil(context, (route) => route.isFirst);
                },
                icon: const Icon(Icons.home),
                label: Text(AppLocalizations.of(context)!.backToHome),
              ),
            ),
          ],
        ),
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
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: 8),
            Text(
              value,
              style: theme.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: theme.textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value, IconData icon) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 20),
          const SizedBox(width: 12),
          Text(
            label,
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          const Spacer(),
          Text(value),
        ],
      ),
    );
  }

  String _calculatePassRate(ScanStatusInfo status) {
    final total = status.passed + status.failed;
    if (total == 0) return '0%';
    final rate = (status.passed / total * 100).toStringAsFixed(1);
    return '$rate%';
  }

  IconData _getStatusIcon(ScanStatus? status) {
    if (status == null) return Icons.help_outline;
    switch (status) {
      case ScanStatus.completed:
        return Icons.check_circle;
      case ScanStatus.failed:
        return Icons.error;
      case ScanStatus.cancelled:
        return Icons.cancel;
      default:
        return Icons.pending;
    }
  }

  Color _getStatusColor(ThemeData theme, ScanStatus? status) {
    if (status == null) return Colors.grey;
    switch (status) {
      case ScanStatus.completed:
        return Colors.green;
      case ScanStatus.failed:
        return Colors.red;
      case ScanStatus.cancelled:
        return Colors.grey;
      default:
        return theme.colorScheme.primary;
    }
  }
}
