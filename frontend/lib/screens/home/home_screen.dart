import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../utils/keyboard_shortcuts.dart';
import '../../widgets/background_scans_indicator.dart';
import '../../providers/api_provider.dart';
import '../../services/api_service.dart';
import '../../providers/background_scans_provider.dart';
import '../configuration/model_selection_screen.dart';
import '../browse/browse_probes_screen.dart';
import '../history/scan_history_screen.dart';
import '../results/enhanced_results_screen.dart';
import '../probes/write_probe_screen.dart';
import '../probes/manage_probes_screen.dart';
import '../settings/settings_screen.dart';
import '../background_tasks/background_tasks_screen.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  List<Map<String, dynamic>>? _recentScans;
  bool _isLoadingRecentScans = true;
  bool _connectionFailed = false;
  bool _isRetrying = false;

  @override
  void initState() {
    super.initState();
    _loadRecentScans();
  }

  Future<void> _loadRecentScans() async {
    try {
      final apiService = ref.read(apiServiceProvider);
      final history = await apiService.getScanHistory();

      // Sort by date (newest first) and take top 5
      history.sort((a, b) {
        final dateA = DateTime.tryParse(a['started_at'] ?? '') ?? DateTime(2000);
        final dateB = DateTime.tryParse(b['started_at'] ?? '') ?? DateTime(2000);
        return dateB.compareTo(dateA);
      });

      if (mounted) {
        setState(() {
          _recentScans = history.take(5).toList();
          _isLoadingRecentScans = false;
          _connectionFailed = false;
          _isRetrying = false;
        });
      }
    } catch (e) {
      if (mounted) {
        // If we got an HTTP status code, the server is reachable (just an API error).
        // Everything else (no response at all) means the server is unreachable.
        final hasHttpResponse = e is ApiException && e.statusCode != null;
        setState(() {
          _recentScans = [];
          _isLoadingRecentScans = false;
          _connectionFailed = !hasHttpResponse;
          _isRetrying = false;
        });
      }
    }
  }

  Future<void> _retryConnection() async {
    setState(() {
      _isRetrying = true;
      _isLoadingRecentScans = true;
    });
    await _loadRecentScans();
  }

  void _navigateToNewScan() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => const ModelSelectionScreen()),
    );
  }

  void _navigateToSettings() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => const SettingsScreen()),
    );
  }

  void _navigateToHistory() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => const ScanHistoryScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final l10n = AppLocalizations.of(context)!;

    return Shortcuts(
      shortcuts: {
        KeyboardShortcuts.newShortcut: const ShortcutIntent('new_scan'),
        KeyboardShortcuts.settingsShortcut: const ShortcutIntent('settings'),
        KeyboardShortcuts.historyShortcut: const ShortcutIntent('history'),
      },
      child: Actions(
        actions: {
          ShortcutIntent: ShortcutCallbackAction({
            'new_scan': _navigateToNewScan,
            'settings': _navigateToSettings,
            'history': _navigateToHistory,
          }),
        },
        child: Focus(
          autofocus: true,
          child: Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.security,
              color: colorScheme.primary,
            ),
            const SizedBox(width: 8),
            Text(
              AppConstants.appName,
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        actions: [
          // Background Tasks icon with badge
          Consumer(
            builder: (context, ref, child) {
              final activeCount = ref.watch(activeBackgroundScanCountProvider);

              return Stack(
                children: [
                  IconButton(
                    icon: const Icon(Icons.alt_route),
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const BackgroundTasksScreen(),
                        ),
                      );
                    },
                    tooltip: 'Background Tasks',
                  ),
                  if (activeCount > 0)
                    Positioned(
                      right: 8,
                      top: 8,
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: colorScheme.error,
                          shape: BoxShape.circle,
                        ),
                        constraints: const BoxConstraints(
                          minWidth: 16,
                          minHeight: 16,
                        ),
                        child: Text(
                          activeCount.toString(),
                          style: TextStyle(
                            color: colorScheme.onError,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
          if (_connectionFailed)
            IconButton(
              icon: _isRetrying
                  ? SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: colorScheme.error,
                      ),
                    )
                  : Icon(Icons.refresh, color: colorScheme.error),
              onPressed: _isRetrying ? null : _retryConnection,
              tooltip: 'Reconnect to server',
            ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: _navigateToSettings,
            tooltip: KeyboardShortcuts.formatHint(l10n.settings, ','),
          ),
          IconButton(
            icon: const Icon(Icons.info_outline),
            onPressed: () {
              _showAboutDialog(context);
            },
            tooltip: l10n.about,
          ),
        ],
      ),
      body: Stack(
        children: [
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppConstants.defaultPadding),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Welcome Section
                  _buildWelcomeCard(context),
                  const SizedBox(height: AppConstants.largePadding),

                  // Connection error banner
                  if (_connectionFailed) ...[
                    _buildConnectionErrorBanner(context),
                    const SizedBox(height: AppConstants.defaultPadding),
                  ],

                  // Actions
                  Text(
                    l10n.actions,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: AppConstants.defaultPadding),
                  _buildQuickActions(context),
                  const SizedBox(height: AppConstants.largePadding),

                  // Recent Scans Section
                  _buildRecentScansSection(context),

                  // Add extra padding at bottom for floating indicator
                  const SizedBox(height: 80),
                ],
              ),
            ),
          ),
          // Floating background scans indicator
          const BackgroundScansIndicator(),
        ],
      ),
      // floatingActionButton: FloatingActionButton.extended(
      //   onPressed: () {
      //     Navigator.push(
      //       context,
      //       MaterialPageRoute(
      //         builder: (context) => const ModelSelectionScreen(),
      //       ),
      //     );
      //   },
      //   icon: const Icon(Icons.add),
      //   label: const Text('New Scan'),
      // ),
          ),
        ),
      ),
    );
  }

  Widget _buildConnectionErrorBanner(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      color: colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(Icons.cloud_off, color: colorScheme.onErrorContainer),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Cannot connect to server',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: colorScheme.onErrorContainer,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Make sure the backend is running and reachable.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.onErrorContainer,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.tonalIcon(
              onPressed: _isRetrying ? null : _retryConnection,
              icon: _isRetrying
                  ? SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: colorScheme.onErrorContainer,
                      ),
                    )
                  : const Icon(Icons.refresh, size: 18),
              label: Text(_isRetrying ? 'Retrying...' : 'Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWelcomeCard(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final l10n = AppLocalizations.of(context)!;

    return Card(
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppConstants.largePadding),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              colorScheme.primaryContainer,
              colorScheme.secondaryContainer,
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(AppConstants.borderRadius),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l10n.llmVulnerabilityScanner,
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: colorScheme.onPrimaryContainer,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.scanDescription,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colorScheme.onPrimaryContainer,
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Icon(
                  Icons.shield_outlined,
                  size: 20,
                  color: colorScheme.onPrimaryContainer,
                ),
                const SizedBox(width: 8),
                Text(
                  l10n.poweredByGarak,
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: colorScheme.onPrimaryContainer,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecentScansSection(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context)!;

    // Don't show section if loading or no scans
    if (_isLoadingRecentScans) {
      return const SizedBox.shrink();
    }

    if (_recentScans == null || _recentScans!.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              l10n.recentScans,
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            TextButton(
              onPressed: _navigateToHistory,
              child: Text(l10n.viewAll),
            ),
          ],
        ),
        const SizedBox(height: AppConstants.smallPadding),
        ..._recentScans!.map((scan) => _buildRecentScanItem(context, scan)),
        const SizedBox(height: AppConstants.largePadding),
      ],
    );
  }

  Widget _buildRecentScanItem(BuildContext context, Map<String, dynamic> scan) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    final scanId = scan['scan_id'] as String?;
    final config = scan['config'] as Map<String, dynamic>?;
    final targetName = scan['target_name'] as String? ??
        config?['target_name'] as String? ??
        'Unknown';
    final status = scan['status'] as String? ?? 'unknown';
    final startedAt = scan['started_at'] as String?;
    final passed = scan['passed'] as int? ?? 0;
    final failed = scan['failed'] as int? ?? 0;

    final startDate = startedAt != null ? DateTime.tryParse(startedAt) : null;
    final statusColor = _getStatusColor(status);
    final isCompleted = status == 'completed';

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: scanId != null && isCompleted
            ? () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => EnhancedResultsScreen(scanId: scanId),
                  ),
                )
            : null,
        borderRadius: BorderRadius.circular(AppConstants.borderRadius),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              // Status icon
              Icon(
                _getStatusIcon(status),
                color: statusColor,
                size: 20,
              ),
              const SizedBox(width: 12),
              // Target name and date
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      targetName,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (startDate != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        DateFormat('MMM d, y HH:mm').format(startDate),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              // Results or status chip
              if (isCompleted && (passed > 0 || failed > 0)) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.green.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '$passed',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: Colors.green,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '$failed',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: Colors.red,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ] else ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    status.toUpperCase(),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: statusColor,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
              // Chevron for completed scans
              if (isCompleted) ...[
                const SizedBox(width: 8),
                Icon(
                  Icons.chevron_right,
                  color: colorScheme.onSurfaceVariant,
                  size: 20,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
        return Colors.green;
      case 'running':
        return Colors.blue;
      case 'failed':
      case 'error':
        return Colors.red;
      case 'cancelled':
        return Colors.orange;
      default:
        return Colors.grey;
    }
  }

  IconData _getStatusIcon(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
        return Icons.check_circle;
      case 'running':
        return Icons.pending;
      case 'failed':
      case 'error':
        return Icons.error;
      case 'cancelled':
        return Icons.cancel;
      default:
        return Icons.help;
    }
  }

  Widget _buildQuickActions(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return LayoutBuilder(
      builder: (context, constraints) {
        final cardWidth = (constraints.maxWidth - AppConstants.defaultPadding) / 2;
        final cardHeight = cardWidth / 1.5;

        return Wrap(
          alignment: WrapAlignment.center,
          spacing: AppConstants.defaultPadding,
          runSpacing: AppConstants.defaultPadding,
          children: [
            SizedBox(
              width: cardWidth,
              height: cardHeight,
              child: _buildActionCard(
                context,
                title: l10n.scan,
                subtitle: l10n.startNewScan,
                icon: Icons.play_circle_outline,
                shortcutHint: '${KeyboardShortcuts.modifierKey}+N',
                onTap: _navigateToNewScan,
              ),
            ),
            SizedBox(
              width: cardWidth,
              height: cardHeight,
              child: _buildActionCard(
                context,
                title: l10n.browseProbesAction,
                subtitle: l10n.viewAllTests,
                icon: Icons.list_alt,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const BrowseProbesScreen(),
                    ),
                  );
                },
              ),
            ),
            SizedBox(
              width: cardWidth,
              height: cardHeight,
              child: _buildActionCard(
                context,
                title: l10n.writeProbe,
                subtitle: l10n.createCustomProbe,
                icon: Icons.code,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const WriteProbeScreen(),
                    ),
                  );
                },
              ),
            ),
            SizedBox(
              width: cardWidth,
              height: cardHeight,
              child: _buildActionCard(
                context,
                title: l10n.myProbes,
                subtitle: l10n.manageSavedProbes,
                icon: Icons.folder_special,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const ManageProbesScreen(),
                    ),
                  );
                },
              ),
            ),
            SizedBox(
              width: cardWidth,
              height: cardHeight,
              child: _buildActionCard(
                context,
                title: l10n.history,
                subtitle: l10n.pastScans,
                icon: Icons.history,
                shortcutHint: '${KeyboardShortcuts.modifierKey}+H',
                onTap: _navigateToHistory,
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildActionCard(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required VoidCallback onTap,
    String? shortcutHint,
  }) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Tooltip(
      message: shortcutHint != null ? '$title ($shortcutHint)' : title,
      child: Card(
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppConstants.borderRadius),
          child: Padding(
            padding: const EdgeInsets.all(AppConstants.defaultPadding),
            child: Stack(
              children: [
                Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      icon,
                      size: 40,
                      color: colorScheme.primary,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
                if (shortcutHint != null)
                  Positioned(
                    top: 0,
                    right: 0,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        shortcutHint,
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                          fontSize: 10,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }


  void _showAboutDialog(BuildContext context) {
    showAboutDialog(
      context: context,
      applicationName: AppConstants.appName,
      applicationVersion: AppConstants.appVersion,
      applicationIcon: const Icon(
        Icons.security,
        size: 48,
      ),
      children: [
        const Text(AppConstants.appDescription),
        const SizedBox(height: 16),
        const Text(
          'A GUI for the LLM vulnerability scanner. '
          'Test your language models for security vulnerabilities, jailbreaks, '
          'prompt injection, and other weaknesses.',
        ),
      ],
    );
  }
}
