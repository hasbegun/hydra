/// Tests for AttemptCard sanitization of control characters in model outputs.
import 'package:flutter_test/flutter_test.dart';
import 'package:hydra/widgets/attempt_card.dart';

import 'package:flutter/material.dart';

void main() {
  group('AttemptCard display', () {
    testWidgets('renders without crashing for normal text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AttemptCard(
              attempt: const {
                'status': 'passed',
                'prompt_text': 'Hello world?',
                'output_text': 'Normal output text.',
                'all_outputs': ['Normal output text.'],
              },
              index: 0,
            ),
          ),
        ),
      );

      expect(find.text('#1'), findsOneWidget);
      expect(find.text('Hello world?'), findsOneWidget);
    });

    testWidgets('renders without crashing for empty output', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AttemptCard(
              attempt: const {
                'status': 'failed',
                'prompt_text': '',
                'output_text': '',
                'all_outputs': <String>[],
              },
              index: 2,
            ),
          ),
        ),
      );

      expect(find.text('#3'), findsOneWidget);
      expect(find.text('(no prompt)'), findsOneWidget);
    });

    testWidgets('shows status icon for failed attempt', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AttemptCard(
              attempt: const {
                'status': 'failed',
                'prompt_text': 'Test prompt',
                'output_text': 'Test output',
                'all_outputs': ['Test output'],
              },
              index: 0,
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.dangerous), findsOneWidget);
    });

    testWidgets('shows status icon for passed attempt', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AttemptCard(
              attempt: const {
                'status': 'passed',
                'prompt_text': 'Test prompt',
                'output_text': 'Test output',
                'all_outputs': ['Test output'],
              },
              index: 0,
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });

    testWidgets('expands on tap to show prompt and output', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: AttemptCard(
                attempt: const {
                  'status': 'failed',
                  'prompt_text': 'What is ANSI?',
                  'output_text': 'ANSI is a standard.',
                  'all_outputs': ['ANSI is a standard.'],
                },
                index: 0,
              ),
            ),
          ),
        ),
      );

      // Before tap: expanded content not visible
      expect(find.text('Prompt'), findsNothing);

      // Tap to expand
      await tester.tap(find.byType(InkWell));
      await tester.pumpAndSettle();

      // After tap: sections visible
      expect(find.text('Prompt'), findsOneWidget);
      expect(find.text('Model Output'), findsOneWidget);
    });

    testWidgets('handles text with escape sequences without crashing',
        (tester) async {
      // Model output containing ANSI escape code text (as strings, not actual bytes)
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: AttemptCard(
                attempt: const {
                  'status': 'failed',
                  'prompt_text': 'Print ANSI codes',
                  'output_text':
                      'Use \\033[4m for underline and \\x1b[0m to reset',
                  'all_outputs': [
                    'Use \\033[4m for underline',
                    'Try [URL] as placeholder',
                  ],
                },
                index: 0,
              ),
            ),
          ),
        ),
      );

      // Tap to expand
      await tester.tap(find.byType(InkWell));
      await tester.pumpAndSettle();

      expect(find.text('All Outputs (2)'), findsOneWidget);
    });

    testWidgets('strips actual binary ESC sequences from output',
        (tester) async {
      // Simulate actual binary ESC byte (0x1b) followed by CSI sequence
      // In Dart, '\x1b' is the actual ESC character
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: AttemptCard(
                attempt: {
                  'status': 'failed',
                  'prompt_text': 'Test binary escapes',
                  'output_text': 'Hello \x1b[32mGREEN\x1b[0m world',
                  'all_outputs': ['Hello \x1b[32mGREEN\x1b[0m world'],
                },
                index: 0,
              ),
            ),
          ),
        ),
      );

      // Tap to expand
      await tester.tap(find.byType(InkWell));
      await tester.pumpAndSettle();

      // The binary ESC sequences should be stripped, leaving clean text
      expect(find.textContaining('Hello GREEN world'), findsWidgets);
    });

    testWidgets('strips binary OSC hyperlink sequences', (tester) async {
      // OSC 8 hyperlink: ESC ] 8 ; params ; uri BEL
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: AttemptCard(
                attempt: {
                  'status': 'failed',
                  'prompt_text': 'Test OSC hyperlink',
                  'output_text':
                      'Click \x1b]8;;https://example.com\x07here\x1b]8;;\x07 to visit',
                  'all_outputs': [
                    'Click \x1b]8;;https://example.com\x07here\x1b]8;;\x07 to visit'
                  ],
                },
                index: 0,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byType(InkWell));
      await tester.pumpAndSettle();

      // OSC sequences stripped, clean text remains
      expect(find.textContaining('Click here to visit'), findsWidgets);
    });

    testWidgets('strips orphaned ]8; remnants', (tester) async {
      // Test ]8;url fragments that appear when ESC prefix was already removed
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: AttemptCard(
                attempt: const {
                  'status': 'failed',
                  'prompt_text': 'Test orphaned fragments',
                  'output_text':
                      'The code is: ]8;http://example.com for links',
                  'all_outputs': [
                    'The code is: ]8;http://example.com for links'
                  ],
                },
                index: 0,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byType(InkWell));
      await tester.pumpAndSettle();

      // ]8;url stripped, clean text remains
      expect(find.textContaining('The code is:  for links'), findsWidgets);
    });

    testWidgets('strips fenced code block markers', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: AttemptCard(
                attempt: const {
                  'status': 'failed',
                  'prompt_text': 'Test code blocks',
                  'output_text': '```plaintext\nsome code\n```',
                  'all_outputs': ['```plaintext\nsome code\n```'],
                },
                index: 0,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byType(InkWell));
      await tester.pumpAndSettle();

      // Code fence markers stripped, content remains
      expect(find.textContaining('some code'), findsWidgets);
    });
  });
}
