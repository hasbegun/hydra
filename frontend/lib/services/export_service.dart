import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:intl/intl.dart';
import '../models/scan_config.dart';

/// Service for exporting scan results in various formats
class ExportService {
  /// Export results as JSON file
  Future<String> exportAsJson(Map<String, dynamic> results, String scanId) async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final timestamp = DateFormat('yyyy-MM-dd_HH-mm-ss').format(DateTime.now());
      final filename = 'garak_scan_${scanId.substring(0, 8)}_$timestamp.json';
      final file = File('${directory.path}/$filename');

      // Pretty print JSON
      final jsonString = const JsonEncoder.withIndent('  ').convert(results);
      await file.writeAsString(jsonString);

      return file.path;
    } catch (e) {
      throw Exception('Failed to export JSON: $e');
    }
  }

  /// Export results as HTML file
  Future<String> exportAsHtml(Map<String, dynamic> results, String scanId) async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final timestamp = DateFormat('yyyy-MM-dd_HH-mm-ss').format(DateTime.now());
      final filename = 'garak_scan_${scanId.substring(0, 8)}_$timestamp.html';
      final file = File('${directory.path}/$filename');

      final html = _generateHtmlReport(results, scanId);
      await file.writeAsString(html);

      return file.path;
    } catch (e) {
      throw Exception('Failed to export HTML: $e');
    }
  }

  /// Export results as PDF file
  Future<String> exportAsPdf(Map<String, dynamic> results, String scanId) async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final timestamp = DateFormat('yyyy-MM-dd_HH-mm-ss').format(DateTime.now());
      final filename = 'garak_scan_${scanId.substring(0, 8)}_$timestamp.pdf';
      final file = File('${directory.path}/$filename');

      final pdf = await _generatePdfReport(results, scanId);
      await file.writeAsBytes(await pdf.save());

      return file.path;
    } catch (e) {
      throw Exception('Failed to export PDF: $e');
    }
  }

  /// Share results using the share dialog
  Future<void> shareResults(Map<String, dynamic> results, String scanId, String format) async {
    try {
      String filePath;

      switch (format.toLowerCase()) {
        case 'json':
          filePath = await exportAsJson(results, scanId);
          break;
        case 'html':
          filePath = await exportAsHtml(results, scanId);
          break;
        case 'pdf':
          filePath = await exportAsPdf(results, scanId);
          break;
        default:
          throw Exception('Unsupported format: $format');
      }

      // Share the file
      await Share.shareXFiles(
        [XFile(filePath)],
        subject: 'Garak Scan Results - ${scanId.substring(0, 8)}',
        text: 'Vulnerability scan results from Garak',
      );
    } catch (e) {
      throw Exception('Failed to share results: $e');
    }
  }

  /// Export scan configuration as JSON file
  Future<String> exportConfig(ScanConfig config) async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final timestamp = DateFormat('yyyy-MM-dd_HH-mm-ss').format(DateTime.now());
      final filename = 'garak_config_$timestamp.json';
      final file = File('${directory.path}/$filename');

      final jsonString = const JsonEncoder.withIndent('  ').convert(config.toJson());
      await file.writeAsString(jsonString);

      return file.path;
    } catch (e) {
      throw Exception('Failed to export config: $e');
    }
  }

  /// Share scan configuration via native share dialog
  Future<void> shareConfig(ScanConfig config) async {
    try {
      final filePath = await exportConfig(config);

      await Share.shareXFiles(
        [XFile(filePath)],
        subject: 'Garak Scan Configuration',
        text: 'Scan configuration exported from Hydra',
      );
    } catch (e) {
      throw Exception('Failed to share config: $e');
    }
  }

  /// Export multiple scan results as a combined JSON file
  Future<String> exportBulkAsJson(List<Map<String, dynamic>> resultsList) async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final timestamp = DateFormat('yyyy-MM-dd_HH-mm-ss').format(DateTime.now());
      final filename = 'garak_bulk_export_${resultsList.length}_scans_$timestamp.json';
      final file = File('${directory.path}/$filename');

      final exportData = {
        'export_info': {
          'exported_at': DateTime.now().toIso8601String(),
          'total_scans': resultsList.length,
          'exported_by': 'Hydra - Garak UI',
        },
        'scans': resultsList,
      };

      final jsonString = const JsonEncoder.withIndent('  ').convert(exportData);
      await file.writeAsString(jsonString);

      return file.path;
    } catch (e) {
      throw Exception('Failed to export bulk JSON: $e');
    }
  }

  /// Export multiple scan results as individual JSON files and return paths
  Future<List<String>> exportBulkAsIndividualJson(List<Map<String, dynamic>> resultsList) async {
    final paths = <String>[];
    for (final results in resultsList) {
      final scanId = results['scan_id'] as String? ?? 'unknown';
      final path = await exportAsJson(results, scanId);
      paths.add(path);
    }
    return paths;
  }

  /// Share multiple scan results
  Future<void> shareBulkResults(List<Map<String, dynamic>> resultsList, String format) async {
    try {
      List<XFile> files = [];

      if (format == 'json_combined') {
        // Single combined JSON file
        final filePath = await exportBulkAsJson(resultsList);
        files.add(XFile(filePath));
      } else {
        // Individual files
        for (final results in resultsList) {
          final scanId = results['scan_id'] as String? ?? 'unknown';
          String filePath;

          switch (format.toLowerCase()) {
            case 'json':
              filePath = await exportAsJson(results, scanId);
              break;
            case 'html':
              filePath = await exportAsHtml(results, scanId);
              break;
            case 'pdf':
              filePath = await exportAsPdf(results, scanId);
              break;
            default:
              throw Exception('Unsupported format: $format');
          }
          files.add(XFile(filePath));
        }
      }

      await Share.shareXFiles(
        files,
        subject: 'Garak Scan Results - ${resultsList.length} scans',
        text: 'Vulnerability scan results from Garak (${resultsList.length} scans)',
      );
    } catch (e) {
      throw Exception('Failed to share bulk results: $e');
    }
  }

  /// Generate HTML report content
  String _generateHtmlReport(Map<String, dynamic> results, String scanId) {
    final summary = results['summary'] ?? {};
    final scanResults = results['results'] ?? {};
    final config = results['config'] ?? {};
    final passed = scanResults['passed'] ?? 0;
    final failed = scanResults['failed'] ?? 0;
    final total = passed + failed;
    final passRate = summary['pass_rate'] ?? 0.0;
    final status = summary['status'] ?? 'Unknown';

    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Garak Scan Results - $scanId</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .header h1 {
            margin: 0 0 10px 0;
        }
        .card {
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        .metric {
            text-align: center;
            padding: 15px;
            border-radius: 8px;
        }
        .metric.passed {
            background: #d4edda;
            color: #155724;
        }
        .metric.failed {
            background: #f8d7da;
            color: #721c24;
        }
        .metric.total {
            background: #d1ecf1;
            color: #0c5460;
        }
        .metric h3 {
            margin: 0;
            font-size: 36px;
        }
        .metric p {
            margin: 5px 0 0 0;
            font-size: 14px;
        }
        .status {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            text-transform: capitalize;
        }
        .status.completed {
            background: #d4edda;
            color: #155724;
        }
        .status.failed {
            background: #f8d7da;
            color: #721c24;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
        }
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: ${passRate >= 80 ? '#28a745' : passRate >= 50 ? '#ffc107' : '#dc3545'};
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #6c757d;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ Garak LLM Vulnerability Scan Report</h1>
        <p>Scan ID: $scanId</p>
        <p>Generated: ${DateTime.now().toString()}</p>
    </div>

    <div class="card">
        <h2>Summary</h2>
        <p>Status: <span class="status $status">$status</span></p>
        <div class="progress-bar">
            <div class="progress-fill" style="width: $passRate%">
                ${passRate.toStringAsFixed(1)}% Pass Rate
            </div>
        </div>
    </div>

    <div class="card">
        <h2>Test Results</h2>
        <div class="summary">
            <div class="metric passed">
                <h3>$passed</h3>
                <p>Tests Passed</p>
            </div>
            <div class="metric failed">
                <h3>$failed</h3>
                <p>Tests Failed</p>
            </div>
            <div class="metric total">
                <h3>$total</h3>
                <p>Total Tests</p>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>Configuration</h2>
        <table>
            <tr>
                <th>Setting</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Target Type</td>
                <td>${config['target_type'] ?? 'N/A'}</td>
            </tr>
            <tr>
                <td>Model</td>
                <td>${config['target_name'] ?? 'N/A'}</td>
            </tr>
            <tr>
                <td>Probes</td>
                <td>${(config['probes'] as List?)?.join(', ') ?? 'N/A'}</td>
            </tr>
            <tr>
                <td>Generations</td>
                <td>${config['generations'] ?? 'N/A'}</td>
            </tr>
            <tr>
                <td>Threshold</td>
                <td>${config['eval_threshold'] ?? 'N/A'}</td>
            </tr>
        </table>
    </div>

    <div class="card">
        <h2>Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Probes</td>
                <td>${scanResults['total_probes'] ?? 0}</td>
            </tr>
            <tr>
                <td>Completed Probes</td>
                <td>${scanResults['completed_probes'] ?? 0}</td>
            </tr>
            <tr>
                <td>Progress</td>
                <td>${(scanResults['progress'] ?? 0).toStringAsFixed(1)}%</td>
            </tr>
        </table>
    </div>

    <div class="footer">
        <p>Generated by Garak UI - LLM Vulnerability Scanner</p>
        <p>Report generated on ${DateFormat('MMMM dd, yyyy at HH:mm').format(DateTime.now())}</p>
    </div>
</body>
</html>
''';
  }

  /// Generate PDF report
  Future<pw.Document> _generatePdfReport(Map<String, dynamic> results, String scanId) async {
    final pdf = pw.Document();
    final summary = results['summary'] ?? {};
    final scanResults = results['results'] ?? {};
    final config = results['config'] ?? {};
    final passed = scanResults['passed'] ?? 0;
    final failed = scanResults['failed'] ?? 0;
    final total = passed + failed;
    final passRate = summary['pass_rate'] ?? 0.0;

    pdf.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        build: (pw.Context context) {
          return [
            // Header
            pw.Header(
              level: 0,
              child: pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Text(
                    'Garak LLM Vulnerability Scan Report',
                    style: pw.TextStyle(fontSize: 24, fontWeight: pw.FontWeight.bold),
                  ),
                  pw.SizedBox(height: 10),
                  pw.Text('Scan ID: $scanId'),
                  pw.Text('Generated: ${DateTime.now()}'),
                ],
              ),
            ),
            pw.SizedBox(height: 20),

            // Summary Section
            pw.Container(
              padding: const pw.EdgeInsets.all(15),
              decoration: pw.BoxDecoration(
                border: pw.Border.all(color: PdfColors.grey300),
                borderRadius: const pw.BorderRadius.all(pw.Radius.circular(8)),
              ),
              child: pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Text(
                    'Summary',
                    style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold),
                  ),
                  pw.SizedBox(height: 10),
                  pw.Text('Status: ${summary['status'] ?? 'Unknown'}'),
                  pw.Text('Pass Rate: ${passRate.toStringAsFixed(1)}%'),
                ],
              ),
            ),
            pw.SizedBox(height: 20),

            // Results Section
            pw.Container(
              padding: const pw.EdgeInsets.all(15),
              decoration: pw.BoxDecoration(
                border: pw.Border.all(color: PdfColors.grey300),
                borderRadius: const pw.BorderRadius.all(pw.Radius.circular(8)),
              ),
              child: pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Text(
                    'Test Results',
                    style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold),
                  ),
                  pw.SizedBox(height: 10),
                  pw.Row(
                    mainAxisAlignment: pw.MainAxisAlignment.spaceAround,
                    children: [
                      _buildPdfMetric('Passed', passed.toString(), PdfColors.green),
                      _buildPdfMetric('Failed', failed.toString(), PdfColors.red),
                      _buildPdfMetric('Total', total.toString(), PdfColors.blue),
                    ],
                  ),
                ],
              ),
            ),
            pw.SizedBox(height: 20),

            // Configuration
            pw.Container(
              padding: const pw.EdgeInsets.all(15),
              decoration: pw.BoxDecoration(
                border: pw.Border.all(color: PdfColors.grey300),
                borderRadius: const pw.BorderRadius.all(pw.Radius.circular(8)),
              ),
              child: pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Text(
                    'Configuration',
                    style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold),
                  ),
                  pw.SizedBox(height: 10),
                  pw.Table(
                    border: pw.TableBorder.all(color: PdfColors.grey300),
                    children: [
                      _buildPdfTableRow('Target Type', config['target_type']?.toString() ?? 'N/A'),
                      _buildPdfTableRow('Model', config['target_name']?.toString() ?? 'N/A'),
                      _buildPdfTableRow('Probes', (config['probes'] as List?)?.join(', ') ?? 'N/A'),
                      _buildPdfTableRow('Generations', config['generations']?.toString() ?? 'N/A'),
                      _buildPdfTableRow('Threshold', config['eval_threshold']?.toString() ?? 'N/A'),
                    ],
                  ),
                ],
              ),
            ),

            // Footer
            pw.SizedBox(height: 30),
            pw.Divider(),
            pw.Center(
              child: pw.Column(
                children: [
                  pw.Text('Generated by Garak UI - LLM Vulnerability Scanner', style: const pw.TextStyle(fontSize: 10)),
                  pw.Text(DateFormat('MMMM dd, yyyy at HH:mm').format(DateTime.now()), style: const pw.TextStyle(fontSize: 10)),
                ],
              ),
            ),
          ];
        },
      ),
    );

    return pdf;
  }

  pw.Widget _buildPdfMetric(String label, String value, PdfColor color) {
    return pw.Container(
      padding: const pw.EdgeInsets.all(10),
      decoration: pw.BoxDecoration(
        color: color.shade(0.1),
        borderRadius: const pw.BorderRadius.all(pw.Radius.circular(8)),
      ),
      child: pw.Column(
        children: [
          pw.Text(value, style: pw.TextStyle(fontSize: 24, fontWeight: pw.FontWeight.bold, color: color)),
          pw.SizedBox(height: 5),
          pw.Text(label, style: const pw.TextStyle(fontSize: 12)),
        ],
      ),
    );
  }

  pw.TableRow _buildPdfTableRow(String label, String value) {
    return pw.TableRow(
      children: [
        pw.Padding(
          padding: const pw.EdgeInsets.all(8),
          child: pw.Text(label, style: pw.TextStyle(fontWeight: pw.FontWeight.bold)),
        ),
        pw.Padding(
          padding: const pw.EdgeInsets.all(8),
          child: pw.Text(value),
        ),
      ],
    );
  }
}
