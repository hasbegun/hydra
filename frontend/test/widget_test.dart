// Basic Flutter widget test for Hydra

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hydra/screens/home/home_screen.dart';
import 'package:hydra/providers/api_provider.dart';
import 'package:hydra/providers/background_scans_provider.dart';
import 'package:hydra/services/background_scan_service.dart';
import 'package:hydra/config/constants.dart';

import 'helpers/pump_app.dart';

void main() {
  testWidgets('App starts and shows home screen', (WidgetTester tester) async {
    final fakeApi = FakeApiService();
    await tester.pumpWidget(buildTestApp(
      home: const HomeScreen(),
      overrides: [
        apiServiceProvider.overrideWith((ref) => fakeApi),
        backgroundScansProvider.overrideWith(
          (ref) => Stream.value(<BackgroundScan>[]),
        ),
        activeBackgroundScanCountProvider.overrideWith((ref) => 0),
      ],
    ));
    await tester.pumpAndSettle();

    // Verify that the app bar shows Hydra
    expect(find.text(AppConstants.appName), findsOneWidget);

    // Verify welcome card is present
    expect(find.text('LLM Vulnerability Scanner'), findsOneWidget);
  });
}
