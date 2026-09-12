import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../models/scan_status.dart';
import '../../services/export_service.dart';
import '../../providers/api_provider.dart';
import '../../widgets/skeleton_loader.dart';
import '../../widgets/breadcrumb_nav.dart';
import '../workflow/workflow_viewer_screen.dart';
import 'detailed_report_screen.dart';
import 'probe_list_view.dart';

/// Enhanced results screen with charts and detailed breakdown
class EnhancedResultsScreen extends ConsumerStatefulWidget {
  final String scanId;
  final ScanStatusInfo? scanStatus;

  const EnhancedResultsScreen({
    super.key,
    required this.scanId,
    this.scanStatus,
  });

  @override
  ConsumerState<EnhancedResultsScreen> createState() => _EnhancedResultsScreenState();
}

class _EnhancedResultsScreenState extends ConsumerState<EnhancedResultsScreen> {
  Map<String, dynamic>? _results;
  bool _isLoading = true;
  String? _error;
  int _touchedIndex = -1;
  final _exportService = ExportService();

  @override
  void initState() {
    super.initState();
    _loadResults();
  }

  Future<void> _loadResults() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final apiService = ref.read(apiServiceProvider);
      final results = await apiService.getScanResults(widget.scanId);

      setState(() {
        _results = results;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load results: $e';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return DefaultTabController(
      length: 4, // Summary, Charts, Probes, Workflow
      child: Scaffold(
        appBar: AppBar(
          title: Text(AppLocalizations.of(context)!.scanResults),
          actions: [
            IconButton(
              icon: const Icon(Icons.share),
              onPressed: _shareResults,
              tooltip: AppLocalizations.of(context)!.shareResults,
            ),
            PopupMenuButton<String>(
              icon: const Icon(Icons.download),
              tooltip: AppLocalizations.of(context)!.export,
              onSelected: _handleExport,
              itemBuilder: (menuContext) => [
                PopupMenuItem(
                  value: 'json',
                  child: Text(AppLocalizations.of(menuContext)!.exportAsJson),
                ),
                PopupMenuItem(
                  value: 'html',
                  child: Text(AppLocalizations.of(menuContext)!.exportAsHtml),
                ),
                PopupMenuItem(
                  value: 'pdf',
                  child: Text(AppLocalizations.of(menuContext)!.exportAsPdf),
                ),
              ],
            ),
          ],
          bottom: _isLoading || _error != null
              ? null
              : const TabBar(
                  isScrollable: true,
                  tabs: [
                    Tab(text: 'Summary', icon: Icon(Icons.dashboard)),
                    Tab(text: 'Charts', icon: Icon(Icons.bar_chart)),
                    Tab(text: 'Probes', icon: Icon(Icons.science)),
                    Tab(text: 'Workflow', icon: Icon(Icons.account_tree)),
                  ],
                ),
        ),
        body: Column(
          children: [
            // Breadcrumb navigation
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
                border: Border(
                  bottom: BorderSide(
                    color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
                  ),
                ),
              ),
              child: BreadcrumbNav(
                items: [
                  BreadcrumbPaths.home(context),
                  BreadcrumbPaths.history(context),
                  BreadcrumbPaths.results(scanId: widget.scanId),
                ],
              ),
            ),
            // Main content
            Expanded(
              child: _isLoading
                  ? const ResultsSummarySkeleton()
                  : _error != null
                      ? _buildErrorView(theme)
                      : TabBarView(
                          children: [
                            _buildSummaryTab(theme),
                            _buildChartsTab(theme),
                            ProbeListView(scanId: widget.scanId),
                            WorkflowViewerScreen(scanId: widget.scanId),
                          ],
                        ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorView(ThemeData theme) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 64, color: theme.colorScheme.error),
          const SizedBox(height: 16),
          Text(AppLocalizations.of(context)!.errorLoadingResults, style: theme.textTheme.titleLarge),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Text(_error!, textAlign: TextAlign.center),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _loadResults,
            icon: const Icon(Icons.refresh),
            label: Text(AppLocalizations.of(context)!.retry),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryTab(ThemeData theme) {
    final summary = _results?['summary'] ?? {};
    final results = _results?['results'] ?? {};
    final passed = results['passed'] ?? 0;
    final failed = results['failed'] ?? 0;
    final total = passed + failed;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppConstants.defaultPadding),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Summary Card
          _buildSummaryCard(theme, summary, passed, failed, total),
          const SizedBox(height: AppConstants.defaultPadding),

          // Detailed Metrics
          _buildMetricsCard(theme, results),
          const SizedBox(height: AppConstants.defaultPadding),

          // Configuration Details
          _buildConfigCard(theme, _results?['config'] ?? {}),
          const SizedBox(height: AppConstants.defaultPadding),

          // Action Buttons
          _buildActionButtons(),
        ],
      ),
    );
  }

  Widget _buildChartsTab(ThemeData theme) {
    final results = _results?['results'] ?? {};
    final passed = results['passed'] ?? 0;
    final failed = results['failed'] ?? 0;
    final total = passed + failed;
    final digest = _results?['digest'] as Map<String, dynamic>?;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppConstants.defaultPadding),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (total > 0) ...[
            _buildChartsCard(theme, passed, failed, total),
            const SizedBox(height: AppConstants.defaultPadding),
            // Probe breakdown chart
            if (digest != null && digest.isNotEmpty) ...[
              _buildProbeBreakdownChart(theme, digest),
              const SizedBox(height: AppConstants.defaultPadding),
              // Vulnerability severity heatmap
              _buildSeverityHeatmap(theme, digest),
            ],
          ] else ...[
            Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.bar_chart, size: 64, color: Colors.grey.shade400),
                    const SizedBox(height: 16),
                    Text(
                      'No chart data available',
                      style: TextStyle(
                        fontSize: 16,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSummaryCard(ThemeData theme, Map<String, dynamic> summary, int passed, int failed, int total) {
    final status = ScanStatus.values.firstWhere(
      (s) => s.name == (summary['status'] ?? 'completed'),
      orElse: () => ScanStatus.completed,
    );
    final passRate = summary['pass_rate'] ?? 0.0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  _getStatusIcon(status),
                  color: _getStatusColor(theme, status),
                  size: 32,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Scan ${status.displayName}',
                        style: theme.textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (summary['error_message'] != null)
                        Text(
                          summary['error_message'],
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.error,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(height: 24),
            Row(
              children: [
                Expanded(
                  child: _buildSummaryItem(
                    theme,
                    AppLocalizations.of(context)!.passRate,
                    '${passRate.toStringAsFixed(1)}%',
                    Icons.check_circle,
                    _getPassRateColor(passRate),
                  ),
                ),
                Expanded(
                  child: _buildSummaryItem(
                    theme,
                    AppLocalizations.of(context)!.totalTests,
                    total.toString(),
                    Icons.assignment,
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

  Widget _buildSummaryItem(ThemeData theme, String label, String value, IconData icon, Color color) {
    return Column(
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
        Text(label, style: theme.textTheme.bodySmall),
      ],
    );
  }

  Widget _buildChartsCard(ThemeData theme, int passed, int failed, int total) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Results Breakdown',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              height: 200,
              child: Row(
                children: [
                  // Pie Chart
                  Expanded(
                    flex: 2,
                    child: PieChart(
                      PieChartData(
                        pieTouchData: PieTouchData(
                          touchCallback: (FlTouchEvent event, pieTouchResponse) {
                            setState(() {
                              if (!event.isInterestedForInteractions ||
                                  pieTouchResponse == null ||
                                  pieTouchResponse.touchedSection == null) {
                                _touchedIndex = -1;
                                return;
                              }
                              _touchedIndex = pieTouchResponse.touchedSection!.touchedSectionIndex;
                            });
                          },
                        ),
                        sectionsSpace: 2,
                        centerSpaceRadius: 40,
                        sections: [
                          PieChartSectionData(
                            color: Colors.green,
                            value: passed.toDouble(),
                            title: passed.toString(),
                            radius: _touchedIndex == 0 ? 60 : 50,
                            titleStyle: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                          PieChartSectionData(
                            color: Colors.red,
                            value: failed.toDouble(),
                            title: failed.toString(),
                            radius: _touchedIndex == 1 ? 60 : 50,
                            titleStyle: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 24),
                  // Legend
                  Expanded(
                    flex: 1,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildLegendItem(AppLocalizations.of(context)!.passed, passed, Colors.green),
                        const SizedBox(height: 12),
                        _buildLegendItem(AppLocalizations.of(context)!.failed, failed, Colors.red),
                      ],
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

  Widget _buildLegendItem(String label, int value, Color color) {
    return Row(
      children: [
        Container(
          width: 16,
          height: 16,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 8),
        Text('$label: $value'),
      ],
    );
  }

  Widget _buildProbeBreakdownChart(ThemeData theme, Map<String, dynamic> digest) {
    // Parse probe data and calculate pass/fail per probe
    final probeData = <_ProbeChartData>[];

    for (final entry in digest.entries) {
      final probeName = entry.key;
      final data = entry.value as Map<String, dynamic>?;
      if (data == null) continue;

      // Extract pass/fail counts from probe data
      final passed = (data['passed'] as num?)?.toInt() ?? 0;
      final failed = (data['failed'] as num?)?.toInt() ?? 0;
      final passRate = data['pass_rate']?.toDouble();

      // Calculate pass rate if not provided
      final total = passed + failed;
      final calculatedPassRate = passRate ?? (total > 0 ? (passed / total * 100) : 0.0);

      if (total > 0) {
        probeData.add(_ProbeChartData(
          name: probeName,
          passed: passed,
          failed: failed,
          passRate: calculatedPassRate,
        ));
      }
    }

    // Sort by pass rate (lowest first to highlight vulnerabilities)
    probeData.sort((a, b) => a.passRate.compareTo(b.passRate));

    if (probeData.isEmpty) {
      return const SizedBox.shrink();
    }

    // Limit to top 15 probes for readability
    final displayData = probeData.take(15).toList();
    final chartHeight = (displayData.length * 40.0).clamp(200.0, 600.0);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.science, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Vulnerability by Probe',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                // Legend
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.green.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(width: 12, height: 12, color: Colors.green),
                      const SizedBox(width: 4),
                      const Text('Pass', style: TextStyle(fontSize: 12)),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(width: 12, height: 12, color: Colors.red),
                      const SizedBox(width: 4),
                      const Text('Fail', style: TextStyle(fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Sorted by pass rate (lowest first)',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: chartHeight,
              child: BarChart(
                BarChartData(
                  alignment: BarChartAlignment.spaceAround,
                  maxY: displayData.map((d) => (d.passed + d.failed).toDouble()).reduce((a, b) => a > b ? a : b) * 1.1,
                  barTouchData: BarTouchData(
                    enabled: true,
                    touchTooltipData: BarTouchTooltipData(
                      getTooltipColor: (group) => theme.colorScheme.surfaceContainerHighest,
                      tooltipPadding: const EdgeInsets.all(8),
                      getTooltipItem: (group, groupIndex, rod, rodIndex) {
                        final probe = displayData[group.x.toInt()];
                        final shortName = _getShortProbeName(probe.name);
                        return BarTooltipItem(
                          '$shortName\n',
                          TextStyle(
                            color: theme.colorScheme.onSurface,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                          children: [
                            TextSpan(
                              text: 'Pass: ${probe.passed}  Fail: ${probe.failed}\n',
                              style: TextStyle(
                                color: theme.colorScheme.onSurfaceVariant,
                                fontSize: 11,
                                fontWeight: FontWeight.normal,
                              ),
                            ),
                            TextSpan(
                              text: 'Rate: ${probe.passRate.toStringAsFixed(1)}%',
                              style: TextStyle(
                                color: _getPassRateColor(probe.passRate),
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        );
                      },
                    ),
                  ),
                  titlesData: FlTitlesData(
                    show: true,
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (value, meta) {
                          if (value < 0 || value >= displayData.length) {
                            return const SizedBox.shrink();
                          }
                          final probe = displayData[value.toInt()];
                          final shortName = _getShortProbeName(probe.name);
                          return SideTitleWidget(
                            axisSide: meta.axisSide,
                            angle: 0.5,
                            child: Text(
                              shortName.length > 12 ? '${shortName.substring(0, 10)}...' : shortName,
                              style: const TextStyle(fontSize: 10),
                            ),
                          );
                        },
                        reservedSize: 60,
                      ),
                    ),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 40,
                        getTitlesWidget: (value, meta) {
                          return Text(
                            value.toInt().toString(),
                            style: const TextStyle(fontSize: 10),
                          );
                        },
                      ),
                    ),
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  ),
                  gridData: FlGridData(
                    show: true,
                    drawVerticalLine: false,
                    horizontalInterval: 5,
                    getDrawingHorizontalLine: (value) => FlLine(
                      color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
                      strokeWidth: 1,
                    ),
                  ),
                  borderData: FlBorderData(show: false),
                  barGroups: displayData.asMap().entries.map((entry) {
                    final index = entry.key;
                    final probe = entry.value;
                    return BarChartGroupData(
                      x: index,
                      barRods: [
                        BarChartRodData(
                          toY: (probe.passed + probe.failed).toDouble(),
                          rodStackItems: [
                            BarChartRodStackItem(0, probe.passed.toDouble(), Colors.green),
                            BarChartRodStackItem(
                              probe.passed.toDouble(),
                              (probe.passed + probe.failed).toDouble(),
                              Colors.red,
                            ),
                          ],
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
                          width: 20,
                        ),
                      ],
                    );
                  }).toList(),
                ),
              ),
            ),
            if (probeData.length > 15) ...[
              const SizedBox(height: 12),
              Center(
                child: Text(
                  'Showing 15 of ${probeData.length} probes (sorted by vulnerability)',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSeverityHeatmap(ThemeData theme, Map<String, dynamic> digest) {
    // Group probes by category and calculate aggregate pass rates
    final categoryData = <String, _CategoryHeatmapData>{};

    for (final entry in digest.entries) {
      final probeName = entry.key;
      final data = entry.value as Map<String, dynamic>?;
      if (data == null) continue;

      // Extract category from probe name (e.g., "garak.probes.dan.Dan_11_0" -> "dan")
      final category = _extractProbeCategory(probeName);
      final passed = (data['passed'] as num?)?.toInt() ?? 0;
      final failed = (data['failed'] as num?)?.toInt() ?? 0;

      if (passed + failed > 0) {
        if (!categoryData.containsKey(category)) {
          categoryData[category] = _CategoryHeatmapData(category: category);
        }
        categoryData[category]!.addProbe(passed, failed);
      }
    }

    if (categoryData.isEmpty) {
      return const SizedBox.shrink();
    }

    // Sort by pass rate (lowest first to highlight vulnerable categories)
    final sortedCategories = categoryData.values.toList()
      ..sort((a, b) => a.passRate.compareTo(b.passRate));

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.grid_on, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Vulnerability Severity Heatmap',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Pass rate by probe category (hover for details)',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            // Severity legend
            _buildSeverityLegend(theme),
            const SizedBox(height: 16),
            // Heatmap grid
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: sortedCategories.map((data) {
                return _buildHeatmapCell(theme, data);
              }).toList(),
            ),
            const SizedBox(height: 16),
            // Summary stats
            _buildHeatmapSummary(theme, sortedCategories),
          ],
        ),
      ),
    );
  }

  Widget _buildSeverityLegend(ThemeData theme) {
    final severityLevels = [
      ('Critical', Colors.red.shade700, '0-20%'),
      ('High', Colors.red.shade400, '20-40%'),
      ('Medium', Colors.orange, '40-60%'),
      ('Low', Colors.yellow.shade700, '60-80%'),
      ('Safe', Colors.green, '80-100%'),
    ];

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          Text(
            'Severity: ',
            style: theme.textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(width: 8),
          ...severityLevels.map((level) {
            final (label, color, range) = level;
            return Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 16,
                    height: 16,
                    decoration: BoxDecoration(
                      color: color,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    '$label ($range)',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildHeatmapCell(ThemeData theme, _CategoryHeatmapData data) {
    final color = _getSeverityColor(data.passRate);
    final textColor = data.passRate < 50 ? Colors.white : Colors.black87;

    return Tooltip(
      message: '${data.category}\n'
          'Pass Rate: ${data.passRate.toStringAsFixed(1)}%\n'
          'Passed: ${data.totalPassed}\n'
          'Failed: ${data.totalFailed}\n'
          'Probes: ${data.probeCount}',
      child: InkWell(
        onTap: () {
          _showCategoryDetails(theme, data);
        },
        borderRadius: BorderRadius.circular(8),
        child: Container(
          width: 100,
          height: 80,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(8),
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: 0.4),
                blurRadius: 4,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                _formatCategoryName(data.category),
                style: TextStyle(
                  color: textColor,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              Text(
                '${data.passRate.toStringAsFixed(0)}%',
                style: TextStyle(
                  color: textColor,
                  fontWeight: FontWeight.bold,
                  fontSize: 18,
                ),
              ),
              Text(
                '${data.probeCount} probes',
                style: TextStyle(
                  color: textColor.withValues(alpha: 0.8),
                  fontSize: 10,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showCategoryDetails(ThemeData theme, _CategoryHeatmapData data) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Container(
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                color: _getSeverityColor(data.passRate),
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(_formatCategoryName(data.category)),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildDetailRow('Pass Rate', '${data.passRate.toStringAsFixed(1)}%', _getSeverityColor(data.passRate)),
            _buildDetailRow('Tests Passed', data.totalPassed.toString(), Colors.green),
            _buildDetailRow('Tests Failed', data.totalFailed.toString(), Colors.red),
            _buildDetailRow('Total Tests', (data.totalPassed + data.totalFailed).toString(), theme.colorScheme.primary),
            _buildDetailRow('Probes Tested', data.probeCount.toString(), theme.colorScheme.secondary),
            const Divider(height: 24),
            Text(
              'Severity Level: ${_getSeverityLabel(data.passRate)}',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: _getSeverityColor(data.passRate),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeatmapSummary(ThemeData theme, List<_CategoryHeatmapData> categories) {
    final criticalCount = categories.where((c) => c.passRate < 20).length;
    final highCount = categories.where((c) => c.passRate >= 20 && c.passRate < 40).length;
    final mediumCount = categories.where((c) => c.passRate >= 40 && c.passRate < 60).length;
    final lowCount = categories.where((c) => c.passRate >= 60 && c.passRate < 80).length;
    final safeCount = categories.where((c) => c.passRate >= 80).length;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _buildHeatmapSummaryItem('Critical', criticalCount, Colors.red.shade700),
          _buildHeatmapSummaryItem('High', highCount, Colors.red.shade400),
          _buildHeatmapSummaryItem('Medium', mediumCount, Colors.orange),
          _buildHeatmapSummaryItem('Low', lowCount, Colors.yellow.shade700),
          _buildHeatmapSummaryItem('Safe', safeCount, Colors.green),
        ],
      ),
    );
  }

  Widget _buildHeatmapSummaryItem(String label, int count, Color color) {
    return Column(
      children: [
        Text(
          count.toString(),
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 10),
        ),
      ],
    );
  }

  String _extractProbeCategory(String probeName) {
    // Extract category from full probe name
    // e.g., "garak.probes.dan.Dan_11_0" -> "dan"
    // e.g., "probes.encoding.InjectBase64" -> "encoding"
    final parts = probeName.split('.');
    if (parts.length >= 3) {
      // Look for "probes" in the path and get the next segment
      final probesIndex = parts.indexOf('probes');
      if (probesIndex >= 0 && probesIndex + 1 < parts.length) {
        return parts[probesIndex + 1];
      }
    }
    // Fallback: use second to last segment or full name
    if (parts.length >= 2) {
      return parts[parts.length - 2];
    }
    return probeName;
  }

  String _formatCategoryName(String category) {
    // Convert category names to title case and expand abbreviations
    final nameMap = {
      'dan': 'DAN Jailbreak',
      'encoding': 'Encoding',
      'xss': 'XSS Attacks',
      'continuation': 'Continuation',
      'gcg': 'GCG Attack',
      'goodside': 'Goodside',
      'knownbadsigs': 'Known Bad Sigs',
      'leakreplay': 'Leak Replay',
      'lmrc': 'LMRC',
      'malwaregen': 'Malware Gen',
      'misleading': 'Misleading',
      'packagehallucination': 'Package Halluc.',
      'promptinject': 'Prompt Inject',
      'realtoxicityprompts': 'Toxic Prompts',
      'snowball': 'Snowball',
      'suffix': 'Suffix Attack',
      'tap': 'TAP Attack',
      'test': 'Test',
      'visual_jailbreak': 'Visual Jailbreak',
    };
    return nameMap[category.toLowerCase()] ??
           category.split('_').map((w) => w.isNotEmpty ? '${w[0].toUpperCase()}${w.substring(1)}' : w).join(' ');
  }

  Color _getSeverityColor(double passRate) {
    if (passRate < 20) return Colors.red.shade700;
    if (passRate < 40) return Colors.red.shade400;
    if (passRate < 60) return Colors.orange;
    if (passRate < 80) return Colors.yellow.shade700;
    return Colors.green;
  }

  String _getSeverityLabel(double passRate) {
    if (passRate < 20) return 'Critical';
    if (passRate < 40) return 'High';
    if (passRate < 60) return 'Medium';
    if (passRate < 80) return 'Low';
    return 'Safe';
  }

  String _getShortProbeName(String fullName) {
    // Extract just the probe class name from full module path
    // e.g., "garak.probes.encoding.InjectBase64" -> "InjectBase64"
    final parts = fullName.split('.');
    return parts.isNotEmpty ? parts.last : fullName;
  }

  Widget _buildMetricsCard(ThemeData theme, Map<String, dynamic> results) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Detailed Metrics',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            _buildMetricRow(Icons.check_circle, 'Tests Passed', results['passed'].toString(), Colors.green),
            const SizedBox(height: 8),
            _buildMetricRow(Icons.error, 'Tests Failed', results['failed'].toString(), Colors.red),
            const SizedBox(height: 8),
            _buildMetricRow(Icons.science, 'Total Probes', results['total_probes'].toString(), theme.colorScheme.primary),
            const SizedBox(height: 8),
            _buildMetricRow(Icons.done_all, 'Completed Probes', results['completed_probes'].toString(), theme.colorScheme.primary),
            if (_results?['duration'] != null) ...[
              const SizedBox(height: 8),
              _buildMetricRow(Icons.timer, 'Duration', _formatDuration(_results!['duration']), theme.colorScheme.secondary),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMetricRow(IconData icon, String label, String value, Color color) {
    return Row(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(width: 12),
        Expanded(child: Text(label)),
        Text(
          value,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ],
    );
  }

  Widget _buildConfigCard(ThemeData theme, Map<String, dynamic> config) {
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
            const SizedBox(height: 16),
            _buildConfigRow('Target Type', config['target_type']?.toString() ?? 'N/A'),
            _buildConfigRow('Model', config['target_name']?.toString() ?? 'N/A'),
            _buildConfigRow('Probes', (config['probes'] as List?)?.join(', ') ?? 'N/A'),
            _buildConfigRow('Generations', config['generations']?.toString() ?? 'N/A'),
            _buildConfigRow('Threshold', config['eval_threshold']?.toString() ?? 'N/A'),
          ],
        ),
      ),
    );
  }

  Widget _buildConfigRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              '$label:',
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
          Expanded(
            child: Text(value),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons() {
    // Check if detailed report is available
    final bool hasDetailedReport = _hasDetailedReport();

    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.home),
            label: Text(AppLocalizations.of(context)!.backToHome),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: FilledButton.icon(
            onPressed: hasDetailedReport ? _viewDetailedReport : null,
            icon: const Icon(Icons.article),
            label: Text(
              hasDetailedReport
                ? AppLocalizations.of(context)!.detailedReport
                : 'No Detailed Report'
            ),
          ),
        ),
      ],
    );
  }

  bool _hasDetailedReport() {
    if (_results == null) return false;

    // Check if any probe has enhanced details
    final digest = _results!['digest'] as Map<String, dynamic>?;
    if (digest == null) return false;

    // Check if there's at least one probe with enhanced details
    for (final entry in digest.entries) {
      final probeData = entry.value as Map<String, dynamic>?;
      if (probeData != null &&
          probeData['has_enhanced_details'] == true) {
        return true;
      }
    }

    return false;
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

  Color _getPassRateColor(double passRate) {
    if (passRate >= 80) return Colors.green;
    if (passRate >= 50) return Colors.orange;
    return Colors.red;
  }

  String _formatDuration(double seconds) {
    final duration = Duration(seconds: seconds.toInt());
    final hours = duration.inHours;
    final minutes = duration.inMinutes.remainder(60);
    final secs = duration.inSeconds.remainder(60);

    if (hours > 0) {
      return '${hours}h ${minutes}m ${secs}s';
    } else if (minutes > 0) {
      return '${minutes}m ${secs}s';
    } else {
      return '${secs}s';
    }
  }

  Future<void> _shareResults() async {
    if (_results == null) return;

    try {
      // Show loading dialog
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => const AlertDialog(
          content: Row(
            children: [
              CircularProgressIndicator(),
              SizedBox(width: 20),
              Text('Preparing to share...'),
            ],
          ),
        ),
      );

      // Share as JSON by default
      await _exportService.shareResults(_results!, widget.scanId, 'json');

      if (mounted) {
        Navigator.pop(context); // Close loading dialog
      }
    } catch (e) {
      if (mounted) {
        Navigator.pop(context); // Close loading dialog
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to share: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _handleExport(String format) async {
    if (_results == null) return;

    try {
      // Show loading dialog
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          content: Row(
            children: [
              const CircularProgressIndicator(),
              const SizedBox(width: 20),
              Text('Exporting as $format...'),
            ],
          ),
        ),
      );

      String filePath;
      switch (format.toLowerCase()) {
        case 'json':
          filePath = await _exportService.exportAsJson(_results!, widget.scanId);
          break;
        case 'html':
          filePath = await _exportService.exportAsHtml(_results!, widget.scanId);
          break;
        case 'pdf':
          filePath = await _exportService.exportAsPdf(_results!, widget.scanId);
          break;
        default:
          throw Exception('Unsupported format');
      }

      if (mounted) {
        Navigator.pop(context); // Close loading dialog

        // Show success dialog
        showDialog(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: Text(AppLocalizations.of(dialogContext)!.exportSuccessful),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('File saved to:'),
                const SizedBox(height: 8),
                SelectableText(
                  filePath,
                  style: TextStyle(fontSize: 12, fontFamily: 'monospace'),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: Text(AppLocalizations.of(dialogContext)!.ok),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        Navigator.pop(context); // Close loading dialog
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Export failed: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _viewDetailedReport() async {
    if (_results == null) return;

    // Navigate to detailed report screen
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => DetailedReportScreen(scanId: widget.scanId),
      ),
    );
  }

  Future<void> _openHtmlReport() async {
    try {
      final apiService = ref.read(apiServiceProvider);
      final reportUrl = Uri.parse('${apiService.baseUrl}/scan/${widget.scanId}/report/html');

      if (await canLaunchUrl(reportUrl)) {
        await launchUrl(reportUrl, mode: LaunchMode.externalApplication);
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Unable to open HTML report'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error opening report: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _showOutputLinesDialog() {
    final outputLines = _results!['output_lines'] as List?;

    showDialog(
      context: context,
      builder: (dialogContext) => Dialog.fullscreen(
        child: Scaffold(
          appBar: AppBar(
            title: Text(AppLocalizations.of(dialogContext)!.detailedScanReport),
            leading: IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => Navigator.pop(dialogContext),
            ),
          ),
          body: outputLines != null && outputLines.isNotEmpty
              ? ListView.builder(
                  padding: const EdgeInsets.all(AppConstants.defaultPadding),
                  itemCount: outputLines.length,
                  itemBuilder: (context, index) {
                    final line = outputLines[index].toString();
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: SelectableText(
                        line,
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: _getLogLineColor(line),
                        ),
                      ),
                    );
                  },
                )
              : const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.article_outlined, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text('No detailed report available'),
                      SizedBox(height: 8),
                      Text(
                        'HTML report was not generated',
                        style: TextStyle(color: Colors.grey),
                      ),
                    ],
                  ),
                ),
        ),
      ),
    );
  }

  Color? _getLogLineColor(String line) {
    final lowerLine = line.toLowerCase();
    if (lowerLine.contains('error') || lowerLine.contains('failed')) {
      return Colors.red[300];
    } else if (lowerLine.contains('warning')) {
      return Colors.orange[300];
    } else if (lowerLine.contains('success') || lowerLine.contains('passed')) {
      return Colors.green[300];
    } else if (lowerLine.contains('probes.')) {
      return Colors.blue[300];
    }
    return null;
  }
}

/// Helper class to hold probe chart data
class _ProbeChartData {
  final String name;
  final int passed;
  final int failed;
  final double passRate;

  _ProbeChartData({
    required this.name,
    required this.passed,
    required this.failed,
    required this.passRate,
  });
}

/// Helper class to hold aggregated category data for heatmap
class _CategoryHeatmapData {
  final String category;
  int totalPassed = 0;
  int totalFailed = 0;
  int probeCount = 0;

  _CategoryHeatmapData({required this.category});

  void addProbe(int passed, int failed) {
    totalPassed += passed;
    totalFailed += failed;
    probeCount++;
  }

  double get passRate {
    final total = totalPassed + totalFailed;
    if (total == 0) return 0;
    return (totalPassed / total) * 100;
  }
}
