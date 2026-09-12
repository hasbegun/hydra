import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:hydra/l10n/app_localizations.dart';
import '../../providers/api_provider.dart';
import '../../widgets/breadcrumb_nav.dart';

class DetailedReportScreen extends ConsumerStatefulWidget {
  final String scanId;

  const DetailedReportScreen({
    super.key,
    required this.scanId,
  });

  @override
  ConsumerState<DetailedReportScreen> createState() => _DetailedReportScreenState();
}

class _DetailedReportScreenState extends ConsumerState<DetailedReportScreen> {
  late final WebViewController _controller;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _initializeWebView();
  }

  void _initializeWebView() {
    final apiService = ref.read(apiServiceProvider);
    final reportUrl = '${apiService.baseUrl}/scan/${widget.scanId}/report/detailed';

    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (String url) {
            setState(() {
              _isLoading = true;
            });
          },
          onPageFinished: (String url) {
            setState(() {
              _isLoading = false;
            });
          },
          onWebResourceError: (WebResourceError error) {
            setState(() {
              _error = error.description;
              _isLoading = false;
            });
          },
        ),
      )
      ..loadRequest(Uri.parse(reportUrl));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context)!.detailedReport),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              _controller.reload();
            },
            tooltip: 'Reload',
          ),
        ],
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
                BreadcrumbPaths.history(context, onTap: () {
                  // Pop twice to get back to history (past results screen)
                  Navigator.of(context).pop();
                  Navigator.of(context).pop();
                }),
                BreadcrumbItem(
                  label: 'Results',
                  icon: Icons.assessment,
                  onTap: () => Navigator.of(context).pop(),
                ),
                BreadcrumbPaths.detailedReport(),
              ],
            ),
          ),
          // Main content
          Expanded(
            child: Stack(
              children: [
                if (_error != null)
                  Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.error_outline,
                    size: 64,
                    color: Colors.red,
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Error Loading Report',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 32),
                    child: Text(
                      _error!,
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 24),
                  FilledButton.icon(
                    onPressed: () {
                      setState(() {
                        _error = null;
                      });
                      _initializeWebView();
                    },
                    icon: const Icon(Icons.refresh),
                    label: Text(AppLocalizations.of(context)!.retry),
                  ),
                ],
              ),
            )
          else
            WebViewWidget(controller: _controller),
          if (_isLoading)
            const Center(
              child: CircularProgressIndicator(),
            ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
