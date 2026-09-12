/// Widget tests for AdvancedConfigScreen.
///
/// Verifies the advanced configuration screen renders correctly with:
/// - Appbar title and export icon
/// - Buffs and Detectors sections (empty and populated states)
/// - Advanced parameters (text fields, toggles, sliders)
/// - Action buttons (Start Scan, Back)
/// - M21 config file text field, M22 report threshold, M23 hit rate slider,
///   and M24 collect timing controls
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hydra/screens/configuration/advanced_config_screen.dart';
import 'package:hydra/providers/scan_config_provider.dart';
import 'package:hydra/providers/plugins_provider.dart';
import 'package:hydra/models/plugin.dart';

import 'helpers/pump_app.dart';

void main() {
  group('AdvancedConfigScreen', () {
    List<Override> createOverrides({
      List<PluginInfo> buffs = const [],
      List<PluginInfo> detectors = const [],
    }) {
      return [
        scanConfigProvider.overrideWith((ref) {
          final notifier = ScanConfigNotifier();
          notifier.setTarget('ollama', 'llama3.2:3b');
          return notifier;
        }),
        buffsProvider.overrideWith((ref) async => buffs),
        detectorsProvider.overrideWith((ref) async => detectors),
      ];
    }

    /// Pump widget and wait for async FutureProviders to resolve.
    Future<void> pumpScreen(
      WidgetTester tester, {
      List<PluginInfo> buffs = const [],
      List<PluginInfo> detectors = const [],
    }) async {
      await tester.pumpWidget(buildTestApp(
        home: const AdvancedConfigScreen(),
        overrides: createOverrides(buffs: buffs, detectors: detectors),
      ));
      // Pump multiple times to allow FutureProviders to resolve
      // (loading → data transition)
      await tester.pump();
      await tester.pump();
      await tester.pump();
    }

    testWidgets('renders appbar with Advanced Configuration title',
        (tester) async {
      await pumpScreen(tester);
      expect(find.text('Advanced Configuration'), findsOneWidget);
    });

    testWidgets('shows Advanced Options heading', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Advanced Options'), findsOneWidget);
    });

    testWidgets('shows subtitle text', (tester) async {
      await pumpScreen(tester);
      expect(
        find.text(
            'Optional: Configure buffs, detectors, and advanced parameters'),
        findsOneWidget,
      );
    });

    testWidgets('shows buffs section header', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Buffs (Input Transformations)'), findsOneWidget);
    });

    testWidgets('shows buffs description', (tester) async {
      await pumpScreen(tester);
      expect(
        find.text(
            'Buffs modify prompts before testing (e.g., paraphrasing, translation)'),
        findsOneWidget,
      );
    });

    testWidgets('shows detectors section header', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Detectors'), findsOneWidget);
    });

    testWidgets('shows detectors description', (tester) async {
      await pumpScreen(tester);
      expect(
        find.text(
            'Detectors analyze model outputs to identify vulnerabilities'),
        findsOneWidget,
      );
    });

    testWidgets('shows "No buffs available" when list empty', (tester) async {
      await pumpScreen(tester);
      expect(find.text('No buffs available'), findsOneWidget);
    });

    testWidgets('shows "No detectors available" when list empty',
        (tester) async {
      await pumpScreen(tester);
      expect(find.text('No detectors available'), findsOneWidget);
    });

    testWidgets('shows buff chips when data available', (tester) async {
      await pumpScreen(
        tester,
        buffs: const [
          PluginInfo(
            name: 'Paraphrase',
            fullName: 'buffs.paraphrase.Paraphrase',
            active: true,
          ),
          PluginInfo(
            name: 'Translate',
            fullName: 'buffs.translate.Translate',
            active: true,
          ),
        ],
      );

      expect(find.text('Paraphrase'), findsOneWidget);
      expect(find.text('Translate'), findsOneWidget);
    });

    testWidgets('shows detector chips when data available', (tester) async {
      await pumpScreen(
        tester,
        detectors: const [
          PluginInfo(
            name: 'Toxicity',
            fullName: 'detectors.toxicity.Toxicity',
            active: true,
          ),
          PluginInfo(
            name: 'Always.Pass',
            fullName: 'detectors.always.Pass',
            active: true,
          ),
        ],
      );

      expect(find.text('Toxicity'), findsOneWidget);
      expect(find.text('Always.Pass'), findsOneWidget);
    });

    testWidgets('shows Advanced Parameters section', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Advanced Parameters'), findsOneWidget);
    });

    testWidgets('shows Start Scan button', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Start Scan'), findsOneWidget);
    });

    testWidgets('shows Back button', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Back'), findsOneWidget);
    });

    testWidgets('shows export icon in appbar', (tester) async {
      await pumpScreen(tester);
      expect(find.byIcon(Icons.file_download), findsOneWidget);
    });

    testWidgets('shows Include Original Prompt toggle', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Include Original Prompt'), findsOneWidget);
    });

    testWidgets('shows Extended Detectors toggle', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Extended Detectors'), findsOneWidget);
    });

    testWidgets('shows Deprefix toggle', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Deprefix'), findsOneWidget);
    });

    testWidgets('shows Skip Unknown Plugins toggle', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Skip Unknown Plugins'), findsOneWidget);
    });

    testWidgets('shows Skip Report Generation toggle', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Skip Report Generation'), findsOneWidget);
    });

    testWidgets('shows Continue on Error toggle', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Continue on Error'), findsOneWidget);
    });

    testWidgets('shows Collect Timing toggle (M24)', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Collect Timing'), findsOneWidget);
      expect(find.text('Record timing metrics for each probe'), findsOneWidget);
    });

    testWidgets('shows Report Threshold slider (M22)', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Report Threshold'), findsOneWidget);
      expect(
        find.text('Only report results above this threshold (0 = report all)'),
        findsOneWidget,
      );
    });

    testWidgets('shows Probe Timeout slider', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Probe Timeout'), findsOneWidget);
      expect(
        find.text('Time limit for each probe (0 = use default)'),
        findsOneWidget,
      );
    });

    testWidgets('shows Verbosity selector with all levels', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Verbosity'), findsOneWidget);
      expect(find.text('Off'), findsOneWidget);
      expect(find.text('-v'), findsOneWidget);
      expect(find.text('-vv'), findsOneWidget);
      expect(find.text('-vvv'), findsOneWidget);
    });

    testWidgets('shows text input fields', (tester) async {
      await pumpScreen(tester);
      expect(find.text('System Prompt'), findsOneWidget);
      expect(find.text('Report Prefix'), findsOneWidget);
      expect(find.text('Output Directory'), findsOneWidget);
      expect(find.text('Exclude Probes'), findsOneWidget);
      expect(find.text('Exclude Detectors'), findsOneWidget);
      expect(find.text('Config File'), findsOneWidget);
    });

    testWidgets('shows Config File text field with helper text (M21)',
        (tester) async {
      await pumpScreen(tester);
      expect(find.text('Config File'), findsOneWidget);
      expect(
        find.text('Path to a YAML/JSON config file for garak (optional)'),
        findsOneWidget,
      );
    });

    testWidgets('shows Hit Rate slider (M23)', (tester) async {
      await pumpScreen(tester);
      expect(find.text('Hit Rate'), findsOneWidget);
      expect(
        find.text(
            'Stop scanning a probe after this hit rate is reached (0 = no limit)'),
        findsOneWidget,
      );
    });

    testWidgets('shows info hint about default values', (tester) async {
      await pumpScreen(tester);
      expect(
        find.text('Leave fields empty to use default values'),
        findsOneWidget,
      );
    });

    testWidgets('can tap a buff chip to select it', (tester) async {
      await pumpScreen(
        tester,
        buffs: const [
          PluginInfo(
            name: 'Paraphrase',
            fullName: 'buffs.paraphrase.Paraphrase',
            active: true,
          ),
        ],
      );

      // Tap the buff chip
      await tester.tap(find.text('Paraphrase'));
      await tester.pump();

      // Should show selection count
      expect(find.text('1 buff(s) selected'), findsOneWidget);
    });

    testWidgets('can toggle Collect Timing switch', (tester) async {
      await pumpScreen(tester);

      // Find the Collect Timing switch
      final switchFinder = find.byWidgetPredicate(
        (widget) =>
            widget is SwitchListTile &&
            widget.title is Text &&
            (widget.title as Text).data == 'Collect Timing',
      );
      expect(switchFinder, findsOneWidget);

      // Initially off
      final switchWidget = tester.widget<SwitchListTile>(switchFinder);
      expect(switchWidget.value, isFalse);

      // Scroll into view before tapping
      await tester.ensureVisible(switchFinder);
      await tester.pump();
      await tester.tap(switchFinder);
      await tester.pump();

      // Now on
      final updatedSwitch = tester.widget<SwitchListTile>(switchFinder);
      expect(updatedSwitch.value, isTrue);
    });

    testWidgets('can toggle Continue on Error switch', (tester) async {
      await pumpScreen(tester);

      final switchFinder = find.byWidgetPredicate(
        (widget) =>
            widget is SwitchListTile &&
            widget.title is Text &&
            (widget.title as Text).data == 'Continue on Error',
      );
      expect(switchFinder, findsOneWidget);

      final switchWidget = tester.widget<SwitchListTile>(switchFinder);
      expect(switchWidget.value, isFalse);

      // Scroll into view before tapping
      await tester.ensureVisible(switchFinder);
      await tester.pump();
      await tester.tap(switchFinder);
      await tester.pump();

      final updatedSwitch = tester.widget<SwitchListTile>(switchFinder);
      expect(updatedSwitch.value, isTrue);
    });
  });
}
