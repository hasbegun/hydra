import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../providers/api_provider.dart';
import '../../services/export_service.dart';
import '../../widgets/empty_state_widget.dart';
import '../../widgets/skeleton_loader.dart';
import '../../models/pagination.dart';
import '../results/enhanced_results_screen.dart';
import '../results/scan_comparison_screen.dart';

class ScanHistoryScreen extends ConsumerStatefulWidget {
  const ScanHistoryScreen({super.key});

  @override
  ConsumerState<ScanHistoryScreen> createState() => _ScanHistoryScreenState();
}

class _ScanHistoryScreenState extends ConsumerState<ScanHistoryScreen> {
  List<Map<String, dynamic>>? _scanHistory;
  bool _isLoading = true;
  String? _error;
  String _searchQuery = '';
  String _sortBy = 'date';
  String? _statusFilter; // null means "all"
  DateTimeRange? _dateRange; // null means "all time"
  final TextEditingController _searchController = TextEditingController();

  // Selection mode state
  bool _isSelectionMode = false;
  final Set<String> _selectedScanIds = {};
  bool _isDeleting = false;
  bool _isExporting = false;
  final _exportService = ExportService();

  // Pagination state
  int _currentPage = 1;
  int _pageSize = 20;
  int _totalPages = 1;
  int _totalItems = 0;
  PaginationMeta? _paginationMeta;
  bool _usePagination = true; // Toggle to use server-side pagination

  // Page size options
  static const List<int> _pageSizeOptions = [10, 20, 50, 100];

  // Quick date range presets
  static const List<(String, int?)> _datePresets = [
    ('All time', null),
    ('Today', 0),
    ('Last 7 days', 7),
    ('Last 30 days', 30),
    ('Last 90 days', 90),
  ];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadHistory({bool resetPage = false}) async {
    if (resetPage) {
      _currentPage = 1;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final apiService = ref.read(apiServiceProvider);

      if (_usePagination) {
        // Use paginated API
        final sortField = _getSortField();
        final sortOrder = _sortBy == 'date' ? SortOrder.desc : SortOrder.asc;

        final response = await apiService.getScanHistoryPaginated(
          page: _currentPage,
          pageSize: _pageSize,
          sortBy: sortField,
          sortOrder: sortOrder,
          status: _statusFilter,
          search: _searchQuery.isNotEmpty ? _searchQuery : null,
          startDate: _dateRange != null
              ? '${_dateRange!.start.year}-${_dateRange!.start.month.toString().padLeft(2, '0')}-${_dateRange!.start.day.toString().padLeft(2, '0')}'
              : null,
          endDate: _dateRange != null
              ? '${_dateRange!.end.year}-${_dateRange!.end.month.toString().padLeft(2, '0')}-${_dateRange!.end.day.toString().padLeft(2, '0')}'
              : null,
        );

        setState(() {
          _scanHistory = response.scans.map((s) => s.toMap()).toList();
          _paginationMeta = response.pagination;
          _totalPages = response.pagination.totalPages;
          _totalItems = response.pagination.totalItems;
          _isLoading = false;
        });
      } else {
        // Fallback to legacy API
        final history = await apiService.getScanHistory();

        setState(() {
          _scanHistory = history;
          _totalItems = history.length;
          _totalPages = 1;
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  ScanSortField _getSortField() {
    switch (_sortBy) {
      case 'date':
        return ScanSortField.startedAt;
      case 'status':
        return ScanSortField.status;
      case 'name':
        return ScanSortField.targetName;
      default:
        return ScanSortField.startedAt;
    }
  }

  void _goToPage(int page) {
    if (page < 1 || page > _totalPages) return;
    _currentPage = page;
    _loadHistory();
  }

  void _changePageSize(int newSize) {
    _pageSize = newSize;
    _currentPage = 1; // Reset to first page
    _loadHistory();
  }

  Future<void> _confirmDelete(String scanId) async {
    final l10n = AppLocalizations.of(context)!;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Scan'),
        content: const Text('Are you sure you want to delete this scan? This will remove all associated reports and cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      await _deleteScan(scanId);
    }
  }

  Future<void> _deleteScan(String scanId) async {
    // Remove the scan from the UI list immediately
    setState(() {
      _scanHistory?.removeWhere((scan) => scan['scan_id'] == scanId);
    });

    try {
      final apiService = ref.read(apiServiceProvider);
      await apiService.deleteScan(scanId);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Scan deleted successfully'),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      // Scan already removed from UI, just log and show info message
      // The scan entry is gone from the UI regardless of backend state
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Scan removed from history'),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 2),
          ),
        );
      }
    }
  }

  List<Map<String, dynamic>> get _filteredAndSortedScans {
    if (_scanHistory == null) return [];

    // When using server-side pagination, filtering/sorting/date range is done by the server
    if (_usePagination) {
      return _scanHistory!;
    }

    // Legacy client-side filtering and sorting
    var scans = _scanHistory!;

    // Apply date range filter
    if (_dateRange != null) {
      final startOfDay = DateTime(_dateRange!.start.year, _dateRange!.start.month, _dateRange!.start.day);
      final endOfDay = DateTime(_dateRange!.end.year, _dateRange!.end.month, _dateRange!.end.day, 23, 59, 59);
      scans = scans.where((scan) {
        final startDate = DateTime.tryParse(scan['started_at'] ?? '');
        if (startDate == null) return false;
        return startDate.isAfter(startOfDay.subtract(const Duration(seconds: 1))) &&
               startDate.isBefore(endOfDay.add(const Duration(seconds: 1)));
      }).toList();
    }

    // Apply status filter
    if (_statusFilter != null) {
      scans = scans.where((scan) {
        final status = scan['status']?.toString().toLowerCase() ?? '';
        return status == _statusFilter;
      }).toList();
    }

    // Apply search query
    if (_searchQuery.isNotEmpty) {
      scans = scans.where((scan) {
        final scanId = scan['scan_id']?.toString().toLowerCase() ?? '';
        // target_name can be at top level (historical scans) or nested in config (active scans)
        final config = scan['config'] as Map<String, dynamic>?;
        final targetName = (scan['target_name']?.toString() ?? config?['target_name']?.toString() ?? '').toLowerCase();
        final status = scan['status']?.toString().toLowerCase() ?? '';
        final startedAt = scan['started_at']?.toString().toLowerCase() ?? '';
        // Format date for searching (e.g., "dec 3, 2025")
        String formattedDate = '';
        final startDate = DateTime.tryParse(scan['started_at'] ?? '');
        if (startDate != null) {
          formattedDate = DateFormat('MMM d, y HH:mm').format(startDate).toLowerCase();
        }
        return scanId.contains(_searchQuery) ||
               targetName.contains(_searchQuery) ||
               status.contains(_searchQuery) ||
               startedAt.contains(_searchQuery) ||
               formattedDate.contains(_searchQuery);
      }).toList();
    }

    scans.sort((a, b) {
      switch (_sortBy) {
        case 'date':
          final dateA = DateTime.tryParse(a['started_at'] ?? '') ?? DateTime(2000);
          final dateB = DateTime.tryParse(b['started_at'] ?? '') ?? DateTime(2000);
          return dateB.compareTo(dateA);
        case 'status':
          return (a['status']?.toString() ?? '').compareTo(b['status']?.toString() ?? '');
        case 'name':
          // target_name can be at top level or nested in config
          final configA = a['config'] as Map<String, dynamic>?;
          final configB = b['config'] as Map<String, dynamic>?;
          final nameA = a['target_name']?.toString() ?? configA?['target_name']?.toString() ?? '';
          final nameB = b['target_name']?.toString() ?? configB?['target_name']?.toString() ?? '';
          return nameA.compareTo(nameB);
        default:
          return 0;
      }
    });

    return scans;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: _isSelectionMode
          ? AppBar(
              leading: IconButton(
                icon: const Icon(Icons.close),
                onPressed: _exitSelectionMode,
                tooltip: 'Cancel selection',
              ),
              title: Text('${_selectedScanIds.length} selected'),
              actions: [
                // Select all button
                IconButton(
                  icon: Icon(
                    _selectedScanIds.length == _filteredAndSortedScans.length
                        ? Icons.deselect
                        : Icons.select_all,
                  ),
                  onPressed: _toggleSelectAll,
                  tooltip: _selectedScanIds.length == _filteredAndSortedScans.length
                      ? 'Deselect all'
                      : 'Select all',
                ),
                // Compare button (only enabled when exactly 2 scans selected)
                IconButton(
                  icon: const Icon(Icons.compare_arrows),
                  onPressed: _selectedScanIds.length == 2 ? _compareSelectedScans : null,
                  tooltip: _selectedScanIds.length == 2
                      ? 'Compare selected scans'
                      : 'Select exactly 2 scans to compare',
                ),
                // Export button
                PopupMenuButton<String>(
                  icon: const Icon(Icons.download),
                  tooltip: 'Export selected',
                  enabled: _selectedScanIds.isNotEmpty,
                  onSelected: _handleBulkExport,
                  itemBuilder: (context) => [
                    const PopupMenuItem(
                      value: 'json_combined',
                      child: ListTile(
                        leading: Icon(Icons.file_present),
                        title: Text('Combined JSON'),
                        subtitle: Text('Single file with all scans'),
                        contentPadding: EdgeInsets.zero,
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'json',
                      child: ListTile(
                        leading: Icon(Icons.data_object),
                        title: Text('Individual JSON'),
                        subtitle: Text('Separate files per scan'),
                        contentPadding: EdgeInsets.zero,
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'html',
                      child: ListTile(
                        leading: Icon(Icons.html),
                        title: Text('HTML Reports'),
                        subtitle: Text('Styled reports per scan'),
                        contentPadding: EdgeInsets.zero,
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'pdf',
                      child: ListTile(
                        leading: Icon(Icons.picture_as_pdf),
                        title: Text('PDF Reports'),
                        subtitle: Text('PDF documents per scan'),
                        contentPadding: EdgeInsets.zero,
                      ),
                    ),
                  ],
                ),
                // Delete button
                IconButton(
                  icon: const Icon(Icons.delete),
                  onPressed: _selectedScanIds.isEmpty ? null : _confirmBulkDelete,
                  tooltip: 'Delete selected',
                ),
              ],
            )
          : AppBar(
              title: Text(l10n.scanHistory),
              actions: [
                // Enter selection mode
                IconButton(
                  icon: const Icon(Icons.checklist),
                  onPressed: _scanHistory != null && _scanHistory!.isNotEmpty
                      ? _enterSelectionMode
                      : null,
                  tooltip: 'Select multiple',
                ),
                IconButton(
                  icon: const Icon(Icons.refresh),
                  onPressed: _loadHistory,
                  tooltip: l10n.refresh,
                ),
                PopupMenuButton<String>(
                  icon: const Icon(Icons.sort),
                  onSelected: (value) {
                    setState(() => _sortBy = value);
                    if (_usePagination) {
                      _loadHistory(resetPage: true);
                    }
                  },
                  itemBuilder: (context) => [
                    PopupMenuItem(value: 'date', child: Text(l10n.sortByDate)),
                    PopupMenuItem(value: 'status', child: Text(l10n.sortByStatus)),
                    PopupMenuItem(value: 'name', child: Text(l10n.sortByName)),
                  ],
                ),
              ],
            ),
      body: _buildBody(theme),
    );
  }

  void _enterSelectionMode() {
    setState(() {
      _isSelectionMode = true;
      _selectedScanIds.clear();
    });
  }

  void _exitSelectionMode() {
    setState(() {
      _isSelectionMode = false;
      _selectedScanIds.clear();
    });
  }

  void _toggleSelectAll() {
    final allScanIds = _filteredAndSortedScans
        .map((scan) => scan['scan_id'] as String?)
        .whereType<String>()
        .toSet();

    setState(() {
      if (_selectedScanIds.length == allScanIds.length) {
        _selectedScanIds.clear();
      } else {
        _selectedScanIds.clear();
        _selectedScanIds.addAll(allScanIds);
      }
    });
  }

  void _toggleScanSelection(String scanId) {
    setState(() {
      if (_selectedScanIds.contains(scanId)) {
        _selectedScanIds.remove(scanId);
        // Exit selection mode if no items selected
        if (_selectedScanIds.isEmpty) {
          _isSelectionMode = false;
        }
      } else {
        _selectedScanIds.add(scanId);
      }
    });
  }

  void _compareSelectedScans() {
    if (_selectedScanIds.length != 2) return;

    final scanIds = _selectedScanIds.toList();

    // Get scan info for labels
    String? labelA;
    String? labelB;
    if (_scanHistory != null) {
      for (final scan in _scanHistory!) {
        final id = scan['scan_id'] as String?;
        if (id == scanIds[0]) {
          final config = scan['config'] as Map<String, dynamic>?;
          labelA = scan['target_name'] as String? ?? config?['target_name'] as String?;
        } else if (id == scanIds[1]) {
          final config = scan['config'] as Map<String, dynamic>?;
          labelB = scan['target_name'] as String? ?? config?['target_name'] as String?;
        }
      }
    }

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ScanComparisonScreen(
          scanIdA: scanIds[0],
          scanIdB: scanIds[1],
          labelA: labelA,
          labelB: labelB,
        ),
      ),
    );
  }

  Future<void> _confirmBulkDelete() async {
    final count = _selectedScanIds.length;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Scans'),
        content: Text(
          'Are you sure you want to delete $count ${count == 1 ? 'scan' : 'scans'}? '
          'This will remove all associated reports and cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      await _bulkDeleteScans();
    }
  }

  Future<void> _bulkDeleteScans() async {
    setState(() => _isDeleting = true);

    final scanIdsToDelete = _selectedScanIds.toList();
    int successCount = 0;
    int failCount = 0;

    try {
      final apiService = ref.read(apiServiceProvider);

      for (final scanId in scanIdsToDelete) {
        try {
          await apiService.deleteScan(scanId);
          successCount++;
          // Remove from local list
          _scanHistory?.removeWhere((scan) => scan['scan_id'] == scanId);
        } catch (e) {
          failCount++;
          // Still remove from local list for UX
          _scanHistory?.removeWhere((scan) => scan['scan_id'] == scanId);
        }
      }

      if (mounted) {
        _exitSelectionMode();

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              failCount == 0
                  ? 'Deleted $successCount ${successCount == 1 ? 'scan' : 'scans'}'
                  : 'Deleted $successCount, failed to delete $failCount',
            ),
            backgroundColor: failCount == 0 ? Colors.green : Colors.orange,
            duration: const Duration(seconds: 3),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isDeleting = false);
      }
    }
  }

  Future<void> _handleBulkExport(String format) async {
    setState(() => _isExporting = true);

    try {
      final apiService = ref.read(apiServiceProvider);
      final resultsList = <Map<String, dynamic>>[];

      // Fetch results for each selected scan
      for (final scanId in _selectedScanIds) {
        try {
          final results = await apiService.getScanResults(scanId);
          results['scan_id'] = scanId; // Ensure scan_id is included
          resultsList.add(results);
        } catch (e) {
          // Skip scans that fail to load
          debugPrint('Failed to load results for $scanId: $e');
        }
      }

      if (resultsList.isEmpty) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('No scan results available for export'),
              backgroundColor: Colors.orange,
            ),
          );
        }
        return;
      }

      // Export using the export service
      await _exportService.shareBulkResults(resultsList, format);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Exported ${resultsList.length} ${resultsList.length == 1 ? 'scan' : 'scans'}'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Export failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isExporting = false);
      }
    }
  }

  Widget _buildBody(ThemeData theme) {
    final l10n = AppLocalizations.of(context)!;

    if (_isLoading || _isDeleting || _isExporting) {
      return Stack(
        children: [
          const ScanHistoryListSkeleton(),
          if (_isDeleting || _isExporting)
            Container(
              color: Colors.black26,
              child: Center(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(),
                        const SizedBox(height: 16),
                        Text(
                          _isDeleting
                              ? 'Deleting ${_selectedScanIds.length} ${_selectedScanIds.length == 1 ? 'scan' : 'scans'}...'
                              : 'Exporting ${_selectedScanIds.length} ${_selectedScanIds.length == 1 ? 'scan' : 'scans'}...',
                          style: theme.textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      );
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: theme.colorScheme.error),
            const SizedBox(height: 16),
            Text(l10n.failedToLoadScanHistory),
            const SizedBox(height: 8),
            Text(_error!, style: theme.textTheme.bodySmall, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _loadHistory,
              icon: const Icon(Icons.refresh),
              label: Text(l10n.retry),
            ),
          ],
        ),
      );
    }

    if (_scanHistory == null || _scanHistory!.isEmpty) {
      return EmptyStateWidget(
        type: EmptyStateType.noHistory,
        title: l10n.noScanHistory,
        message: l10n.noScanHistoryMessage,
      );
    }

    final filteredScans = _filteredAndSortedScans;

    return Column(
      children: [
        // Search field
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppConstants.defaultPadding,
            AppConstants.defaultPadding,
            AppConstants.defaultPadding,
            8,
          ),
          child: TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: l10n.searchScans,
              helperText: 'Search by name, date, status, or scan ID',
              helperStyle: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
              prefixIcon: const Icon(Icons.search),
              border: const OutlineInputBorder(),
              suffixIcon: _searchQuery.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _searchController.clear();
                        setState(() => _searchQuery = '');
                      },
                    )
                  : null,
            ),
            onChanged: (value) {
              setState(() => _searchQuery = value.toLowerCase());
              // Reload with server-side search after a brief delay
              if (_usePagination) {
                Future.delayed(const Duration(milliseconds: 500), () {
                  if (_searchQuery == value.toLowerCase()) {
                    _loadHistory(resetPage: true);
                  }
                });
              }
            },
          ),
        ),
        // Filter row with status and date
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppConstants.defaultPadding),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Status filter chips
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildStatusChip(null, 'All', Icons.list),
                    const SizedBox(width: 8),
                    _buildStatusChip('completed', 'Completed', Icons.check_circle),
                    const SizedBox(width: 8),
                    _buildStatusChip('running', 'Running', Icons.pending),
                    const SizedBox(width: 8),
                    _buildStatusChip('failed', 'Failed', Icons.error),
                    const SizedBox(width: 8),
                    _buildStatusChip('cancelled', 'Cancelled', Icons.cancel),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              // Date range filter
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    Icon(
                      Icons.calendar_today,
                      size: 16,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                    const SizedBox(width: 8),
                    ..._datePresets.map((preset) {
                      final (label, days) = preset;
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: _buildDatePresetChip(label, days),
                      );
                    }),
                    // Custom date range button
                    ActionChip(
                      avatar: const Icon(Icons.date_range, size: 16),
                      label: const Text('Custom'),
                      onPressed: _showDateRangePicker,
                    ),
                  ],
                ),
              ),
              // Show selected custom date range
              if (_dateRange != null && !_isPresetDateRange()) ...[
                const SizedBox(height: 4),
                Text(
                  '${DateFormat('MMM d, y').format(_dateRange!.start)} - ${DateFormat('MMM d, y').format(_dateRange!.end)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.primary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 8),
        // Results count and clear filters
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppConstants.defaultPadding),
          child: Row(
            children: [
              Text(
                _usePagination
                    ? 'Showing ${filteredScans.length} of $_totalItems ${_totalItems == 1 ? 'scan' : 'scans'}'
                    : '${filteredScans.length} ${filteredScans.length == 1 ? 'scan' : 'scans'}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (_hasActiveFilters) ...[
                const SizedBox(width: 8),
                TextButton.icon(
                  onPressed: _clearAllFilters,
                  icon: const Icon(Icons.clear_all, size: 16),
                  label: const Text('Clear filters'),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 8),
        // Scan list
        Expanded(
          child: filteredScans.isEmpty
              ? _buildNoResultsState(theme)
              : ListView.builder(
                  padding: const EdgeInsets.all(AppConstants.defaultPadding),
                  itemCount: filteredScans.length,
                  itemBuilder: (context, index) => _buildScanCard(theme, filteredScans[index]),
                ),
        ),
        // Pagination controls
        if (_usePagination && _totalPages > 0)
          _buildPaginationControls(theme),
      ],
    );
  }

  Widget _buildPaginationControls(ThemeData theme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: Border(
          top: BorderSide(
            color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
      ),
      child: Row(
        children: [
          // Page size selector
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Show:',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(width: 8),
              DropdownButton<int>(
                value: _pageSize,
                underline: const SizedBox.shrink(),
                isDense: true,
                items: _pageSizeOptions.map((size) {
                  return DropdownMenuItem<int>(
                    value: size,
                    child: Text('$size'),
                  );
                }).toList(),
                onChanged: (value) {
                  if (value != null) {
                    _changePageSize(value);
                  }
                },
              ),
            ],
          ),
          const SizedBox(width: 16),
          // Total items info
          Text(
            '$_totalItems ${_totalItems == 1 ? 'scan' : 'scans'}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const Spacer(),
          // Page navigation
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // First page
              IconButton(
                icon: const Icon(Icons.first_page, size: 20),
                onPressed: _currentPage > 1 ? () => _goToPage(1) : null,
                tooltip: 'First page',
                visualDensity: VisualDensity.compact,
              ),
              // Previous page
              IconButton(
                icon: const Icon(Icons.chevron_left, size: 20),
                onPressed: _currentPage > 1 ? () => _goToPage(_currentPage - 1) : null,
                tooltip: 'Previous page',
                visualDensity: VisualDensity.compact,
              ),
              // Page indicator
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'Page $_currentPage of $_totalPages',
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
              // Next page
              IconButton(
                icon: const Icon(Icons.chevron_right, size: 20),
                onPressed: _currentPage < _totalPages ? () => _goToPage(_currentPage + 1) : null,
                tooltip: 'Next page',
                visualDensity: VisualDensity.compact,
              ),
              // Last page
              IconButton(
                icon: const Icon(Icons.last_page, size: 20),
                onPressed: _currentPage < _totalPages ? () => _goToPage(_totalPages) : null,
                tooltip: 'Last page',
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatusChip(String? status, String label, IconData icon) {
    final theme = Theme.of(context);
    final isSelected = _statusFilter == status;
    final color = status == null
        ? theme.colorScheme.primary
        : _getStatusColor(status);

    return FilterChip(
      selected: isSelected,
      label: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 16,
            color: isSelected ? theme.colorScheme.onPrimaryContainer : color,
          ),
          const SizedBox(width: 4),
          Text(label),
        ],
      ),
      onSelected: (selected) {
        setState(() => _statusFilter = selected ? status : null);
        if (_usePagination) {
          _loadHistory(resetPage: true);
        }
      },
      selectedColor: color.withValues(alpha: 0.2),
      checkmarkColor: color,
      labelStyle: TextStyle(
        color: isSelected ? color : theme.colorScheme.onSurface,
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
      ),
    );
  }

  Widget _buildDatePresetChip(String label, int? days) {
    final theme = Theme.of(context);
    final isSelected = _isDatePresetSelected(days);

    return ChoiceChip(
      selected: isSelected,
      label: Text(label),
      onSelected: (selected) {
        setState(() {
          if (selected) {
            _dateRange = _getDateRangeForDays(days);
          } else {
            _dateRange = null;
          }
        });
        if (_usePagination) {
          _loadHistory(resetPage: true);
        }
      },
      selectedColor: theme.colorScheme.primaryContainer,
      labelStyle: TextStyle(
        color: isSelected
            ? theme.colorScheme.onPrimaryContainer
            : theme.colorScheme.onSurface,
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
      ),
    );
  }

  bool _isDatePresetSelected(int? days) {
    if (days == null) return _dateRange == null;
    final presetRange = _getDateRangeForDays(days);
    if (_dateRange == null || presetRange == null) return false;
    return _dateRange!.start.year == presetRange.start.year &&
        _dateRange!.start.month == presetRange.start.month &&
        _dateRange!.start.day == presetRange.start.day &&
        _dateRange!.end.year == presetRange.end.year &&
        _dateRange!.end.month == presetRange.end.month &&
        _dateRange!.end.day == presetRange.end.day;
  }

  DateTimeRange? _getDateRangeForDays(int? days) {
    if (days == null) return null;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    if (days == 0) {
      // Today
      return DateTimeRange(start: today, end: today);
    }
    return DateTimeRange(
      start: today.subtract(Duration(days: days - 1)),
      end: today,
    );
  }

  bool _isPresetDateRange() {
    for (final preset in _datePresets) {
      final (_, days) = preset;
      if (_isDatePresetSelected(days)) return true;
    }
    return false;
  }

  Future<void> _showDateRangePicker() async {
    final now = DateTime.now();
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: now,
      initialDateRange: _dateRange ?? DateTimeRange(
        start: now.subtract(const Duration(days: 30)),
        end: now,
      ),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: Theme.of(context).colorScheme,
          ),
          child: child!,
        );
      },
    );

    if (picked != null) {
      setState(() => _dateRange = picked);
      if (_usePagination) {
        _loadHistory(resetPage: true);
      }
    }
  }

  bool get _hasActiveFilters =>
      _statusFilter != null || _searchQuery.isNotEmpty || _dateRange != null;

  void _clearAllFilters() {
    setState(() {
      _statusFilter = null;
      _searchQuery = '';
      _searchController.clear();
      _dateRange = null;
    });
    if (_usePagination) {
      _loadHistory(resetPage: true);
    }
  }

  Widget _buildNoResultsState(ThemeData theme) {
    final hasFilters = _hasActiveFilters;

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            hasFilters ? Icons.search_off : Icons.history,
            size: 64,
            color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            hasFilters ? 'No matching scans' : 'No scans yet',
            style: theme.textTheme.titleMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          if (hasFilters) ...[
            const SizedBox(height: 8),
            Text(
              'Try adjusting your search or filters',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _clearAllFilters,
              icon: const Icon(Icons.clear_all),
              label: const Text('Clear all filters'),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildScanCard(ThemeData theme, Map<String, dynamic> scan) {
    final scanId = scan['scan_id'] as String?;
    // target_name can be at top level (historical scans) or nested in config (active scans)
    final config = scan['config'] as Map<String, dynamic>?;
    final targetName = scan['target_name'] as String?
        ?? config?['target_name'] as String?
        ?? 'Unknown';
    final status = scan['status'] as String? ?? 'unknown';
    final startedAt = scan['started_at'] as String?;
    final passed = scan['passed'] as int? ?? 0;
    final failed = scan['failed'] as int? ?? 0;
    final total = passed + failed;

    final startDate = startedAt != null ? DateTime.tryParse(startedAt) : null;
    final statusColor = _getStatusColor(status);
    final isSelected = scanId != null && _selectedScanIds.contains(scanId);

    return Card(
      margin: const EdgeInsets.only(bottom: AppConstants.defaultPadding),
      color: isSelected ? theme.colorScheme.primaryContainer.withValues(alpha: 0.3) : null,
      child: InkWell(
        onTap: _isSelectionMode
            ? (scanId != null ? () => _toggleScanSelection(scanId) : null)
            : (scanId != null && status == 'completed'
                ? () => Navigator.push(context, MaterialPageRoute(builder: (context) => EnhancedResultsScreen(scanId: scanId)))
                : null),
        onLongPress: !_isSelectionMode && scanId != null
            ? () {
                _enterSelectionMode();
                _toggleScanSelection(scanId);
              }
            : null,
        child: Padding(
          padding: const EdgeInsets.all(AppConstants.defaultPadding),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Selection checkbox (only in selection mode)
              if (_isSelectionMode) ...[
                Checkbox(
                  value: isSelected,
                  onChanged: scanId != null
                      ? (value) => _toggleScanSelection(scanId)
                      : null,
                ),
                const SizedBox(width: 8),
              ],
              // Card content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(_getStatusIcon(status), color: statusColor, size: 20),
                        const SizedBox(width: 8),
                        Expanded(child: Text(targetName, style: theme.textTheme.titleMedium)),
                        Chip(
                          label: Text(status.toUpperCase()),
                          labelStyle: theme.textTheme.labelSmall,
                          backgroundColor: statusColor.withValues(alpha: 0.1),
                        ),
                        // Hide delete button in selection mode
                        if (!_isSelectionMode) ...[
                          const SizedBox(width: 8),
                          IconButton(
                            icon: const Icon(Icons.delete_outline, size: 20),
                            onPressed: scanId != null ? () => _confirmDelete(scanId) : null,
                            tooltip: 'Delete scan',
                            color: theme.colorScheme.error,
                          ),
                        ],
                      ],
                    ),
                    if (scanId != null) ...[
                      const SizedBox(height: 8),
                      Text(scanId, style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
                    ],
                    if (startDate != null) ...[
                      const SizedBox(height: 8),
                      Text(DateFormat('MMM d, y HH:mm').format(startDate), style: theme.textTheme.bodySmall),
                    ],
                    if (status == 'completed' && total > 0) ...[
                      const SizedBox(height: 12),
                      const Divider(height: 1),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          _buildResultBadge(theme, 'PASS', passed, total, Colors.green),
                          const SizedBox(width: 8),
                          _buildResultBadge(theme, 'FAIL', failed, total, Colors.red),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResultBadge(ThemeData theme, String label, int count, int total, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: theme.textTheme.labelSmall?.copyWith(fontWeight: FontWeight.bold, color: color)),
          const SizedBox(width: 4),
          Text('$count/$total', style: theme.textTheme.labelSmall?.copyWith(color: color)),
        ],
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
}
