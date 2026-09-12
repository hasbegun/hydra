/// Shared test utilities for widget testing.
///
/// Provides a [buildTestApp] wrapper and [FakeApiService] for mocking
/// API calls without network access.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:hydra/l10n/app_localizations.dart';
import 'package:hydra/services/api_service.dart';
import 'package:hydra/models/plugin.dart';

/// Wraps a widget with MaterialApp + localization + ProviderScope for testing.
Widget buildTestApp({
  required Widget home,
  List<Override> overrides = const [],
}) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: const [Locale('en')],
      locale: const Locale('en'),
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6200EE),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        cardTheme: CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      home: home,
    ),
  );
}

/// Fake API service that returns controlled data without network calls.
class FakeApiService extends ApiService {
  final List<Map<String, dynamic>> scanHistoryData;
  final bool throwOnHistory;

  FakeApiService({
    this.scanHistoryData = const [],
    this.throwOnHistory = false,
  }) : super();

  @override
  Future<List<Map<String, dynamic>>> getScanHistory() async {
    if (throwOnHistory) {
      throw ApiException(message: 'Connection refused');
    }
    return List.from(scanHistoryData);
  }

  @override
  Future<PluginListResponse> listBuffs() async {
    return const PluginListResponse(plugins: [], totalCount: 0);
  }

  @override
  Future<PluginListResponse> listDetectors() async {
    return const PluginListResponse(plugins: [], totalCount: 0);
  }

  @override
  Future<PluginListResponse> listProbes() async {
    return const PluginListResponse(plugins: [], totalCount: 0);
  }

  @override
  Future<PluginListResponse> listGenerators() async {
    return const PluginListResponse(plugins: [], totalCount: 0);
  }
}
