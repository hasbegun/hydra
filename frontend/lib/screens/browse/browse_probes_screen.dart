import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../config/constants.dart';
import '../../providers/plugins_provider.dart';
import '../../models/plugin.dart';

class BrowseProbesScreen extends ConsumerStatefulWidget {
  const BrowseProbesScreen({super.key});

  @override
  ConsumerState<BrowseProbesScreen> createState() => _BrowseProbesScreenState();
}

class _BrowseProbesScreenState extends ConsumerState<BrowseProbesScreen> {
  String _searchQuery = '';
  String? _selectedCategory;
  final Set<String> _expandedCategories = {};

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final categorizedProbes = ref.watch(categorizedProbesProvider);
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.browseProbes),
        actions: [
          IconButton(
            icon: const Icon(Icons.info_outline),
            onPressed: () => _showProbeInfo(context),
          ),
        ],
      ),
      body: categorizedProbes.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.error_outline,
                size: 64,
                color: theme.colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(l10n.failedToLoadProbes),
              const SizedBox(height: 8),
              Text(
                error.toString(),
                style: theme.textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: () => ref.invalidate(categorizedProbesProvider),
                icon: const Icon(Icons.refresh),
                label: Text(l10n.retry),
              ),
            ],
          ),
        ),
        data: (probesByCategory) {
          final categories = probesByCategory.keys.toList()..sort();
          final filteredCategories = _selectedCategory != null
              ? [_selectedCategory!]
              : categories;

          return Column(
            children: [
              // Search and Filter
              Padding(
                padding: const EdgeInsets.all(AppConstants.defaultPadding),
                child: Column(
                  children: [
                    // Search Bar
                    TextField(
                      decoration: InputDecoration(
                        hintText: l10n.searchProbes,
                        prefixIcon: const Icon(Icons.search),
                        border: const OutlineInputBorder(),
                        suffixIcon: _searchQuery.isNotEmpty
                            ? IconButton(
                                icon: const Icon(Icons.clear),
                                onPressed: () {
                                  setState(() {
                                    _searchQuery = '';
                                  });
                                },
                              )
                            : null,
                      ),
                      onChanged: (value) {
                        setState(() {
                          _searchQuery = value.toLowerCase();
                        });
                      },
                    ),
                    const SizedBox(height: 8),
                    // Category Filter
                    SizedBox(
                      height: 40,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        children: [
                          FilterChip(
                            label: Text(l10n.allCategories),
                            selected: _selectedCategory == null,
                            onSelected: (selected) {
                              setState(() {
                                _selectedCategory = null;
                              });
                            },
                          ),
                          const SizedBox(width: 8),
                          ...categories.map((category) {
                            final count = probesByCategory[category]!.length;
                            return Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: FilterChip(
                                label: Text('$category ($count)'),
                                selected: _selectedCategory == category,
                                onSelected: (selected) {
                                  setState(() {
                                    _selectedCategory =
                                        selected ? category : null;
                                  });
                                },
                              ),
                            );
                          }),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              // Probe List
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.all(AppConstants.defaultPadding),
                  itemCount: filteredCategories.length,
                  itemBuilder: (context, index) {
                    final category = filteredCategories[index];
                    final probes = probesByCategory[category]!;
                    final filteredProbes = _searchQuery.isEmpty
                        ? probes
                        : probes
                            .where((probe) =>
                                probe.name.toLowerCase().contains(_searchQuery) ||
                                probe.fullName
                                    .toLowerCase()
                                    .contains(_searchQuery) ||
                                (probe.description
                                        ?.toLowerCase()
                                        .contains(_searchQuery) ??
                                    false))
                            .toList();

                    if (filteredProbes.isEmpty) {
                      return const SizedBox.shrink();
                    }

                    final isExpanded = _expandedCategories.contains(category);

                    return Card(
                      margin: const EdgeInsets.only(
                          bottom: AppConstants.defaultPadding),
                      child: Column(
                        children: [
                          ListTile(
                            leading: Icon(
                              _getCategoryIcon(category),
                              color: theme.colorScheme.primary,
                            ),
                            title: Text(
                              category.toUpperCase(),
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            subtitle: Text(
                              '${filteredProbes.length} probe${filteredProbes.length != 1 ? 's' : ''}',
                              style: theme.textTheme.bodySmall,
                            ),
                            trailing: IconButton(
                              icon: Icon(
                                isExpanded
                                    ? Icons.expand_less
                                    : Icons.expand_more,
                              ),
                              onPressed: () {
                                setState(() {
                                  if (isExpanded) {
                                    _expandedCategories.remove(category);
                                  } else {
                                    _expandedCategories.add(category);
                                  }
                                });
                              },
                            ),
                            onTap: () {
                              setState(() {
                                if (isExpanded) {
                                  _expandedCategories.remove(category);
                                } else {
                                  _expandedCategories.add(category);
                                }
                              });
                            },
                          ),
                          if (isExpanded)
                            ...filteredProbes.map((probe) =>
                                _buildProbeItem(context, theme, probe, category)),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildProbeItem(
    BuildContext context,
    ThemeData theme,
    PluginInfo probe,
    String category,
  ) {
    final l10n = AppLocalizations.of(context)!;

    return InkWell(
      onTap: () => _showProbeDetails(context, probe),
      child: Container(
        padding: const EdgeInsets.all(AppConstants.defaultPadding),
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(
              color: theme.dividerColor,
              width: 1,
            ),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    probe.name,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                if (!probe.active)
                  Chip(
                    label: Text(l10n.inactive),
                    labelStyle: theme.textTheme.labelSmall,
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
            if (probe.description != null) ...[
              const SizedBox(height: 4),
              Text(
                probe.description!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            if (probe.tags != null && probe.tags!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 4,
                runSpacing: 4,
                children: probe.tags!.take(3).map((tag) {
                  return Chip(
                    label: Text(tag),
                    labelStyle: theme.textTheme.labelSmall,
                    visualDensity: VisualDensity.compact,
                    backgroundColor:
                        theme.colorScheme.secondaryContainer.withValues(alpha: 0.5),
                  );
                }).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _showProbeDetails(BuildContext context, PluginInfo probe) {
    final theme = Theme.of(context);
    final category = _extractCategory(probe.fullName);
    final l10n = AppLocalizations.of(context)!;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (context, scrollController) => Container(
          padding: const EdgeInsets.all(AppConstants.largePadding),
          child: ListView(
            controller: scrollController,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      probe.name,
                      style: theme.textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                category.toUpperCase(),
                style: theme.textTheme.labelLarge?.copyWith(
                  color: theme.colorScheme.primary,
                ),
              ),
              const SizedBox(height: 16),
              if (probe.description != null) ...[
                Text(
                  l10n.description,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  probe.description!,
                  style: theme.textTheme.bodyMedium,
                ),
                const SizedBox(height: 16),
              ],
              Text(
                l10n.fullName,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  probe.fullName,
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontFamily: 'monospace',
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                l10n.status,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(
                    probe.active ? Icons.check_circle : Icons.cancel,
                    color: probe.active ? Colors.green : Colors.red,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    probe.active ? l10n.active : l10n.inactive,
                    style: theme.textTheme.bodyMedium,
                  ),
                ],
              ),
              if (probe.tags != null && probe.tags!.isNotEmpty) ...[
                const SizedBox(height: 16),
                Text(
                  l10n.tags,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: probe.tags!.map((tag) {
                    return Chip(
                      label: Text(tag),
                      backgroundColor: theme.colorScheme.secondaryContainer,
                    );
                  }).toList(),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String _extractCategory(String fullName) {
    final parts = fullName.split('.');
    if (parts.length >= 2) {
      return parts[1];
    }
    return 'other';
  }

  IconData _getCategoryIcon(String category) {
    final categoryLower = category.toLowerCase();
    if (categoryLower.contains('inject') || categoryLower.contains('prompt')) {
      return Icons.input;
    } else if (categoryLower.contains('dan') || categoryLower.contains('jail')) {
      return Icons.lock_open;
    } else if (categoryLower.contains('toxic') || categoryLower.contains('harm')) {
      return Icons.warning;
    } else if (categoryLower.contains('encode') || categoryLower.contains('obfusc')) {
      return Icons.transform;
    } else if (categoryLower.contains('leak') || categoryLower.contains('extract')) {
      return Icons.leak_add;
    } else if (categoryLower.contains('malware') || categoryLower.contains('exploit')) {
      return Icons.bug_report;
    } else {
      return Icons.science;
    }
  }

  void _showProbeInfo(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.aboutProbes),
        content: const SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Probes are test modules that check for specific vulnerabilities in language models.',
              ),
              SizedBox(height: 16),
              Text(
                'Common Categories:',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              SizedBox(height: 8),
              Text('• DAN: "Do Anything Now" jailbreak attempts'),
              Text('• Prompt Injection: Attempts to manipulate model behavior'),
              Text('• Encoding: Obfuscation and encoding-based attacks'),
              Text('• Toxicity: Tests for generating harmful content'),
              Text('• Data Leakage: Tests for exposing training data'),
              SizedBox(height: 16),
              Text(
                'Tap on any probe to view detailed information and examples.',
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.gotIt),
          ),
        ],
      ),
    );
  }
}
