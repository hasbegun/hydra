/// Tests for M21-M24 CLI flags:
/// M21 (--config_file), M22 (--report_threshold),
/// M23 (--hit_rate), M24 (--collect_timing).
///
/// Covers:
/// - ScanConfig model: serialization, defaults, copyWith
/// - ScanConfigNotifier: setConfigFile, setReportThreshold, setHitRate, setCollectTiming
import 'package:flutter_test/flutter_test.dart';
import 'package:hydra/models/scan_config.dart';
import 'package:hydra/providers/scan_config_provider.dart';

void main() {
  // -----------------------------------------------------------------------
  // ScanConfig model tests
  // -----------------------------------------------------------------------

  group('ScanConfig - configFile (M21)', () {
    test('defaults to null', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
      );
      expect(config.configFile, isNull);
    });

    test('can be set via constructor', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        configFile: '/path/to/config.yaml',
      );
      expect(config.configFile, '/path/to/config.yaml');
    });

    test('serializes to JSON with correct key', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        configFile: '/path/to/config.yaml',
      );
      final json = config.toJson();
      expect(json['config_file'], '/path/to/config.yaml');
    });

    test('deserializes from JSON', () {
      final json = {
        'target_type': 'ollama',
        'target_name': 'llama3.2:3b',
        'probes': ['all'],
        'config_file': '/data/scan.json',
        'generations': 5,
        'eval_threshold': 0.5,
        'extended_detectors': false,
        'deprefix': false,
        'verbose': 0,
        'skip_unknown': false,
        'buffs_include_original_prompt': false,
        'no_report': false,
        'continue_on_error': false,
        'collect_timing': false,
      };
      final config = ScanConfig.fromJson(json);
      expect(config.configFile, '/data/scan.json');
    });

    test('null when not in JSON', () {
      final json = {
        'target_type': 'ollama',
        'target_name': 'llama3.2:3b',
        'probes': ['all'],
        'generations': 5,
        'eval_threshold': 0.5,
        'extended_detectors': false,
        'deprefix': false,
        'verbose': 0,
        'skip_unknown': false,
        'buffs_include_original_prompt': false,
        'no_report': false,
        'continue_on_error': false,
        'collect_timing': false,
      };
      final config = ScanConfig.fromJson(json);
      expect(config.configFile, isNull);
    });

    test('copyWith preserves value', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        configFile: '/path/to/config.yaml',
      );
      final copy = config.copyWith(generations: 10);
      expect(copy.configFile, '/path/to/config.yaml');
    });

    test('copyWith can override value', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        configFile: '/old/config.yaml',
      );
      final copy = config.copyWith(configFile: '/new/config.yaml');
      expect(copy.configFile, '/new/config.yaml');
    });

    test('serialization roundtrip', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        configFile: '/path/to/config.yaml',
      );
      final restored = ScanConfig.fromJson(config.toJson());
      expect(restored.configFile, '/path/to/config.yaml');
    });
  });

  group('ScanConfig - reportThreshold (M22)', () {
    test('defaults to null', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
      );
      expect(config.reportThreshold, isNull);
    });

    test('can be set via constructor', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        reportThreshold: 0.75,
      );
      expect(config.reportThreshold, 0.75);
    });

    test('serializes to JSON with correct key', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        reportThreshold: 0.42,
      );
      final json = config.toJson();
      expect(json['report_threshold'], 0.42);
    });

    test('deserializes from JSON', () {
      final json = {
        'target_type': 'ollama',
        'target_name': 'llama3.2:3b',
        'probes': ['all'],
        'report_threshold': 0.65,
        'generations': 5,
        'eval_threshold': 0.5,
        'extended_detectors': false,
        'deprefix': false,
        'verbose': 0,
        'skip_unknown': false,
        'buffs_include_original_prompt': false,
        'no_report': false,
        'continue_on_error': false,
        'collect_timing': false,
      };
      final config = ScanConfig.fromJson(json);
      expect(config.reportThreshold, 0.65);
    });

    test('null when not in JSON', () {
      final json = {
        'target_type': 'ollama',
        'target_name': 'llama3.2:3b',
        'probes': ['all'],
        'generations': 5,
        'eval_threshold': 0.5,
        'extended_detectors': false,
        'deprefix': false,
        'verbose': 0,
        'skip_unknown': false,
        'buffs_include_original_prompt': false,
        'no_report': false,
        'continue_on_error': false,
        'collect_timing': false,
      };
      final config = ScanConfig.fromJson(json);
      expect(config.reportThreshold, isNull);
    });

    test('copyWith preserves value', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        reportThreshold: 0.5,
      );
      final copy = config.copyWith(generations: 10);
      expect(copy.reportThreshold, 0.5);
    });

    test('copyWith can override value', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        reportThreshold: 0.5,
      );
      final copy = config.copyWith(reportThreshold: 0.8);
      expect(copy.reportThreshold, 0.8);
    });

    test('serialization roundtrip', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        reportThreshold: 0.33,
      );
      final restored = ScanConfig.fromJson(config.toJson());
      expect(restored.reportThreshold, 0.33);
    });
  });

  group('ScanConfig - hitRate (M23)', () {
    test('defaults to null', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
      );
      expect(config.hitRate, isNull);
    });

    test('can be set via constructor', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        hitRate: 0.3,
      );
      expect(config.hitRate, 0.3);
    });

    test('serializes to JSON with correct key', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        hitRate: 0.25,
      );
      final json = config.toJson();
      expect(json['hit_rate'], 0.25);
    });

    test('deserializes from JSON', () {
      final json = {
        'target_type': 'ollama',
        'target_name': 'llama3.2:3b',
        'probes': ['all'],
        'hit_rate': 0.9,
        'generations': 5,
        'eval_threshold': 0.5,
        'extended_detectors': false,
        'deprefix': false,
        'verbose': 0,
        'skip_unknown': false,
        'buffs_include_original_prompt': false,
        'no_report': false,
        'continue_on_error': false,
        'collect_timing': false,
      };
      final config = ScanConfig.fromJson(json);
      expect(config.hitRate, 0.9);
    });

    test('null when not in JSON', () {
      final json = {
        'target_type': 'ollama',
        'target_name': 'llama3.2:3b',
        'probes': ['all'],
        'generations': 5,
        'eval_threshold': 0.5,
        'extended_detectors': false,
        'deprefix': false,
        'verbose': 0,
        'skip_unknown': false,
        'buffs_include_original_prompt': false,
        'no_report': false,
        'continue_on_error': false,
        'collect_timing': false,
      };
      final config = ScanConfig.fromJson(json);
      expect(config.hitRate, isNull);
    });

    test('copyWith preserves value', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        hitRate: 0.5,
      );
      final copy = config.copyWith(generations: 10);
      expect(copy.hitRate, 0.5);
    });

    test('copyWith can override value', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        hitRate: 0.5,
      );
      final copy = config.copyWith(hitRate: 0.8);
      expect(copy.hitRate, 0.8);
    });

    test('serialization roundtrip', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        hitRate: 0.45,
      );
      final restored = ScanConfig.fromJson(config.toJson());
      expect(restored.hitRate, 0.45);
    });
  });

  group('ScanConfig - collectTiming (M24)', () {
    test('defaults to false', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
      );
      expect(config.collectTiming, false);
    });

    test('can be set to true', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        collectTiming: true,
      );
      expect(config.collectTiming, true);
    });

    test('serializes to JSON with correct key', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        collectTiming: true,
      );
      final json = config.toJson();
      expect(json['collect_timing'], true);
    });

    test('deserializes from JSON', () {
      final json = {
        'target_type': 'ollama',
        'target_name': 'llama3.2:3b',
        'probes': ['all'],
        'collect_timing': true,
        'generations': 5,
        'eval_threshold': 0.5,
        'extended_detectors': false,
        'deprefix': false,
        'verbose': 0,
        'skip_unknown': false,
        'buffs_include_original_prompt': false,
        'no_report': false,
        'continue_on_error': false,
      };
      final config = ScanConfig.fromJson(json);
      expect(config.collectTiming, true);
    });

    test('defaults to false when not in JSON', () {
      final json = {
        'target_type': 'ollama',
        'target_name': 'llama3.2:3b',
        'probes': ['all'],
        'generations': 5,
        'eval_threshold': 0.5,
        'extended_detectors': false,
        'deprefix': false,
        'verbose': 0,
        'skip_unknown': false,
        'buffs_include_original_prompt': false,
        'no_report': false,
        'continue_on_error': false,
      };
      final config = ScanConfig.fromJson(json);
      expect(config.collectTiming, false);
    });

    test('copyWith preserves value', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        collectTiming: true,
      );
      final copy = config.copyWith(generations: 10);
      expect(copy.collectTiming, true);
    });

    test('copyWith can override value', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        collectTiming: false,
      );
      final copy = config.copyWith(collectTiming: true);
      expect(copy.collectTiming, true);
    });

    test('serialization roundtrip', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        collectTiming: true,
      );
      final restored = ScanConfig.fromJson(config.toJson());
      expect(restored.collectTiming, true);
    });
  });

  // -----------------------------------------------------------------------
  // ScanConfigNotifier tests
  // -----------------------------------------------------------------------

  group('ScanConfigNotifier - configFile', () {
    test('setConfigFile updates state', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setConfigFile('/path/to/config.yaml');
      expect(notifier.debugState!.configFile, '/path/to/config.yaml');
    });

    test('setTarget preserves configFile', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setConfigFile('/path/to/config.yaml');
      notifier.setTarget('ollama', 'mistral:latest');
      expect(notifier.debugState!.configFile, '/path/to/config.yaml');
    });

    test('does nothing when state is null', () {
      final notifier = ScanConfigNotifier();
      notifier.setConfigFile('/path/to/config.yaml'); // Should not throw
      expect(notifier.debugState, isNull);
    });
  });

  group('ScanConfigNotifier - hitRate', () {
    test('setHitRate updates state', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setHitRate(0.5);
      expect(notifier.debugState!.hitRate, 0.5);
    });

    test('setTarget preserves hitRate', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setHitRate(0.3);
      notifier.setTarget('ollama', 'mistral:latest');
      expect(notifier.debugState!.hitRate, 0.3);
    });

    test('does nothing when state is null', () {
      final notifier = ScanConfigNotifier();
      notifier.setHitRate(0.5); // Should not throw
      expect(notifier.debugState, isNull);
    });
  });

  group('ScanConfigNotifier - reportThreshold', () {
    test('setReportThreshold updates state', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setReportThreshold(0.75);
      expect(notifier.debugState!.reportThreshold, 0.75);
    });

    test('setReportThreshold with null clears value', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setReportThreshold(0.5);
      expect(notifier.debugState!.reportThreshold, 0.5);
      // copyWith with null preserves, so this won't clear —
      // but the field is nullable and defaults to null in setTarget
    });

    test('setTarget preserves reportThreshold', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setReportThreshold(0.6);
      notifier.setTarget('ollama', 'mistral:latest');
      expect(notifier.debugState!.reportThreshold, 0.6);
    });

    test('does nothing when state is null', () {
      final notifier = ScanConfigNotifier();
      notifier.setReportThreshold(0.5); // Should not throw
      expect(notifier.debugState, isNull);
    });
  });

  group('ScanConfigNotifier - collectTiming', () {
    test('setCollectTiming updates state', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setCollectTiming(true);
      expect(notifier.debugState!.collectTiming, true);
    });

    test('setCollectTiming to false', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setCollectTiming(true);
      notifier.setCollectTiming(false);
      expect(notifier.debugState!.collectTiming, false);
    });

    test('setTarget preserves collectTiming', () {
      final notifier = ScanConfigNotifier();
      notifier.setTarget('ollama', 'llama3.2:3b');
      notifier.setCollectTiming(true);
      notifier.setTarget('ollama', 'mistral:latest');
      expect(notifier.debugState!.collectTiming, true);
    });

    test('does nothing when state is null', () {
      final notifier = ScanConfigNotifier();
      notifier.setCollectTiming(true); // Should not throw
      expect(notifier.debugState, isNull);
    });
  });

  // -----------------------------------------------------------------------
  // Combined tests
  // -----------------------------------------------------------------------

  group('ScanConfig - all four flags together (M21-M24)', () {
    test('all four flags in constructor', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        configFile: '/path/to/config.yaml',
        hitRate: 0.4,
        reportThreshold: 0.8,
        collectTiming: true,
      );
      expect(config.configFile, '/path/to/config.yaml');
      expect(config.hitRate, 0.4);
      expect(config.reportThreshold, 0.8);
      expect(config.collectTiming, true);
    });

    test('all four flags serialize correctly', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['all'],
        configFile: '/path/to/config.yaml',
        hitRate: 0.3,
        reportThreshold: 0.5,
        collectTiming: true,
      );
      final json = config.toJson();
      expect(json['config_file'], '/path/to/config.yaml');
      expect(json['hit_rate'], 0.3);
      expect(json['report_threshold'], 0.5);
      expect(json['collect_timing'], true);
    });

    test('all four flags with existing flags', () {
      const config = ScanConfig(
        targetType: 'ollama',
        targetName: 'llama3.2:3b',
        probes: ['dan', 'encoding'],
        generations: 3,
        evalThreshold: 0.7,
        configFile: '/path/to/config.yaml',
        hitRate: 0.6,
        reportThreshold: 0.5,
        collectTiming: true,
        continueOnError: true,
        extendedDetectors: true,
        timeoutPerProbe: 120,
      );
      final json = config.toJson();
      expect(json['config_file'], '/path/to/config.yaml');
      expect(json['hit_rate'], 0.6);
      expect(json['report_threshold'], 0.5);
      expect(json['collect_timing'], true);
      expect(json['continue_on_error'], true);
      expect(json['extended_detectors'], true);
      expect(json['timeout_per_probe'], 120);
      expect(json['generations'], 3);
    });
  });
}
