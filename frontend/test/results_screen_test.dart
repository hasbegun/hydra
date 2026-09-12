/// Widget tests for ResultsScreen.
///
/// Verifies the results screen renders correctly with:
/// - Scan status header (completed, failed, cancelled)
/// - Summary statistics (total, passed, failed, pass rate)
/// - Probe execution info
/// - Error message display
/// - Action buttons (export, back to home)
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hydra/screens/results/results_screen.dart';
import 'package:hydra/models/scan_status.dart';

import 'helpers/pump_app.dart';

void main() {
  group('ResultsScreen', () {
    testWidgets('renders appbar with Scan Results title', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: const ResultsScreen(scanId: 'test-001'),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Scan Results'), findsOneWidget);
    });

    testWidgets('shows scan ID', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: const ResultsScreen(scanId: 'test-scan-abc'),
      ));
      await tester.pumpAndSettle();

      expect(find.text('ID: test-scan-abc'), findsOneWidget);
    });

    testWidgets('shows "Scan Complete" when no status provided',
        (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: const ResultsScreen(scanId: 'test-001'),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Scan Complete'), findsOneWidget);
    });

    testWidgets('shows "Scan Completed" for completed status',
        (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 5,
            totalProbes: 5,
            passed: 10,
            failed: 3,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Scan Completed'), findsOneWidget);
    });

    testWidgets('shows "Scan Failed" for failed status', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.failed,
            progress: 50.0,
            completedProbes: 2,
            totalProbes: 5,
            passed: 5,
            failed: 3,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Scan Failed'), findsOneWidget);
    });

    testWidgets('shows summary stat labels', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 5,
            totalProbes: 5,
            passed: 20,
            failed: 10,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Summary'), findsOneWidget);
      expect(find.text('Total Tests'), findsOneWidget);
      expect(find.text('Passed'), findsOneWidget);
      expect(find.text('Failed'), findsOneWidget);
      expect(find.text('Pass Rate'), findsOneWidget);
    });

    testWidgets('shows correct summary stat values', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 5,
            totalProbes: 5,
            passed: 20,
            failed: 10,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      // Total = passed + failed = 30
      expect(find.text('30'), findsOneWidget);
      expect(find.text('20'), findsOneWidget);
      expect(find.text('10'), findsOneWidget);
    });

    testWidgets('computes pass rate correctly', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 5,
            totalProbes: 5,
            passed: 15,
            failed: 5,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      // 15 / (15+5) * 100 = 75.0%
      expect(find.text('75.0%'), findsOneWidget);
    });

    testWidgets('shows 0% pass rate when no tests', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 0,
            totalProbes: 0,
            passed: 0,
            failed: 0,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('0%'), findsOneWidget);
    });

    testWidgets('shows 100% pass rate when all pass', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 5,
            totalProbes: 5,
            passed: 25,
            failed: 0,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('100.0%'), findsOneWidget);
    });

    testWidgets('shows probes executed section', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 7,
            totalProbes: 8,
            passed: 10,
            failed: 2,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Probes Executed'), findsOneWidget);
      expect(find.text('Total Probes'), findsOneWidget);
      expect(find.text('Completed'), findsOneWidget);
    });

    testWidgets('shows last probe name when available', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 5,
            totalProbes: 5,
            passed: 10,
            failed: 2,
            currentProbe: 'probes.dan.DAN_Jailbreak',
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Last Probe'), findsOneWidget);
      expect(find.text('probes.dan.DAN_Jailbreak'), findsOneWidget);
    });

    testWidgets('hides last probe row when no current probe', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 5,
            totalProbes: 5,
            passed: 10,
            failed: 0,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Last Probe'), findsNothing);
    });

    testWidgets('shows error message when present', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.failed,
            progress: 50.0,
            completedProbes: 2,
            totalProbes: 5,
            passed: 5,
            failed: 3,
            errorMessage: 'Connection to model timed out',
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Error'), findsOneWidget);
      expect(find.text('Connection to model timed out'), findsOneWidget);
    });

    testWidgets('hides error card when no error', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: ResultsScreen(
          scanId: 'test-001',
          scanStatus: const ScanStatusInfo(
            scanId: 'test-001',
            status: ScanStatus.completed,
            progress: 100.0,
            completedProbes: 5,
            totalProbes: 5,
            passed: 10,
            failed: 0,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Connection to model timed out'), findsNothing);
    });

    testWidgets('shows export button', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: const ResultsScreen(scanId: 'test-001'),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Export Full Report'), findsOneWidget);
    });

    testWidgets('shows back to home button', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: const ResultsScreen(scanId: 'test-001'),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Back to Home'), findsOneWidget);
    });

    testWidgets('shows share and download icons in appbar', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: const ResultsScreen(scanId: 'test-001'),
      ));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.share), findsOneWidget);
      expect(find.byIcon(Icons.download), findsOneWidget);
    });

    testWidgets('shows Actions section', (tester) async {
      await tester.pumpWidget(buildTestApp(
        home: const ResultsScreen(scanId: 'test-001'),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Actions'), findsOneWidget);
    });
  });
}
