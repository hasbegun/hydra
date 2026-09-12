# Agentic Workflow Viewer - MVP Completion Guide

**Status:** Backend Complete (4/4) | Frontend In Progress (2/7)
**Last Updated:** 2025-01-19

---

## Completed Work

### Backend ✅

All backend components are fully functional and ready to capture workflow data:

1. **Data Models** (`backend/models/schemas.py`)
   - WorkflowNode, WorkflowEdge, WorkflowGraph
   - WorkflowTrace, WorkflowTimelineEvent
   - All enum types and validations

2. **WorkflowAnalyzer** (`backend/services/workflow_analyzer.py`)
   - Real-time Garak output parsing
   - Graph building with nodes and edges
   - Export to JSON and Mermaid
   - Timeline generation

3. **API Endpoints** (`backend/api/routes/workflow.py`)
   - `GET /api/v1/scan/{scan_id}/workflow`
   - `GET /api/v1/scan/{scan_id}/workflow/timeline`
   - `POST /api/v1/scan/{scan_id}/workflow/export`
   - `DELETE /api/v1/scan/{scan_id}/workflow`

4. **Integration** (`backend/services/garak_wrapper.py`)
   - WorkflowAnalyzer processes all Garak output
   - Real-time workflow graph building

### Frontend (Partial) ⏳

1. **Dart Models** (`frontend/lib/models/workflow/`)
   - `workflow_node.dart` ✅
   - `workflow_edge.dart` ✅
   - `workflow_graph.dart` ✅

---

## Remaining Work

### Step 1: Generate Freezed Code

The Dart models use `freezed` for immutability. Generate the code:

```bash
cd hydra/frontend
flutter pub get
flutter pub run build_runner build --delete-conflicting-outputs
```

This will generate:
- `workflow_node.freezed.dart`
- `workflow_node.g.dart`
- `workflow_edge.freezed.dart`
- `workflow_edge.g.dart`
- `workflow_graph.freezed.dart`
- `workflow_graph.g.dart`

### Step 2: Install Dependencies

Add to `pubspec.yaml`:

```yaml
dependencies:
  # Existing dependencies...

  # Graph visualization
  graphview: ^1.2.0

  # Already have:
  # - flutter_riverpod
  # - dio
  # - freezed_annotation
  # - json_annotation

dev_dependencies:
  # Already have:
  # - freezed
  # - build_runner
  # - json_serializable
```

Run:
```bash
flutter pub get
```

### Step 3: Create WorkflowService

Create `frontend/lib/services/workflow_service.dart`:

```dart
import 'package:dio/dio.dart';
import '../models/workflow/workflow_graph.dart';

class WorkflowService {
  final Dio _dio;
  final String baseUrl;

  WorkflowService(this._dio, this.baseUrl);

  /// Fetch workflow graph for a scan
  Future<WorkflowGraph> getWorkflowGraph(String scanId) async {
    try {
      final response = await _dio.get('$baseUrl/api/v1/scan/$scanId/workflow');
      return WorkflowGraph.fromJson(response.data);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        throw Exception('No workflow found for scan $scanId');
      }
      rethrow;
    }
  }

  /// Export workflow
  Future<String> exportWorkflow(String scanId, String format) async {
    final response = await _dio.post(
      '$baseUrl/api/v1/scan/$scanId/workflow/export',
      data: {'format': format},
    );
    return response.data['data'] as String;
  }
}
```

### Step 4: Create WorkflowProvider

Create `frontend/lib/providers/workflow_provider.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/workflow/workflow_graph.dart';
import '../services/workflow_service.dart';
import 'api_provider.dart';

/// Workflow state
class WorkflowState {
  final WorkflowGraph? graph;
  final bool isLoading;
  final String? error;

  const WorkflowState({
    this.graph,
    this.isLoading = false,
    this.error,
  });

  WorkflowState copyWith({
    WorkflowGraph? graph,
    bool? isLoading,
    String? error,
  }) {
    return WorkflowState(
      graph: graph ?? this.graph,
      isLoading: isLoading ?? this.isLoading,
      error: error ?? this.error,
    );
  }
}

/// Workflow notifier
class WorkflowNotifier extends StateNotifier<WorkflowState> {
  final WorkflowService _service;
  final String _scanId;

  WorkflowNotifier(this._service, this._scanId)
      : super(const WorkflowState());

  Future<void> loadWorkflow() async {
    state = state.copyWith(isLoading: true, error: null);

    try {
      final graph = await _service.getWorkflowGraph(_scanId);
      state = state.copyWith(graph: graph, isLoading: false);
    } catch (e) {
      state = state.copyWith(
        error: e.toString(),
        isLoading: false,
      );
    }
  }

  Future<void> exportWorkflow(String format) async {
    try {
      await _service.exportWorkflow(_scanId, format);
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }
}

/// Workflow service provider
final workflowServiceProvider = Provider<WorkflowService>((ref) {
  final dio = ref.watch(dioProvider);
  return WorkflowService(dio, 'http://localhost:8888');
});

/// Workflow provider family (by scan_id)
final workflowProvider =
    StateNotifierProvider.family<WorkflowNotifier, WorkflowState, String>(
  (ref, scanId) {
    final service = ref.watch(workflowServiceProvider);
    return WorkflowNotifier(service, scanId);
  },
);
```

### Step 5: Create Basic Graph Widget

Create `frontend/lib/widgets/workflow/workflow_graph_view.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';
import '../../models/workflow/workflow_graph.dart' as model;
import '../../models/workflow/workflow_node.dart';

class WorkflowGraphView extends StatefulWidget {
  final model.WorkflowGraph graph;
  final Function(String nodeId)? onNodeTap;

  const WorkflowGraphView({
    Key? key,
    required this.graph,
    this.onNodeTap,
  }) : super(key: key);

  @override
  State<WorkflowGraphView> createState() => _WorkflowGraphViewState();
}

class _WorkflowGraphViewState extends State<WorkflowGraphView> {
  final Graph graph = Graph()..isTree = true;
  BuchheimWalkerConfiguration builder = BuchheimWalkerConfiguration();

  @override
  void initState() {
    super.initState();
    _buildGraph();

    builder
      ..siblingSeparation = (100)
      ..levelSeparation = (150)
      ..subtreeSeparation = (150)
      ..orientation = (BuchheimWalkerConfiguration.ORIENTATION_TOP_BOTTOM);
  }

  void _buildGraph() {
    // Create nodes
    for (var node in widget.graph.nodes) {
      graph.addNode(Node.Id(node.nodeId));
    }

    // Create edges
    for (var edge in widget.graph.edges) {
      try {
        final source = graph.getNodeUsingId(edge.sourceId);
        final target = graph.getNodeUsingId(edge.targetId);
        graph.addEdge(source, target);
      } catch (e) {
        // Skip invalid edges
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.graph.isEmpty) {
      return Center(
        child: Text('No workflow data available'),
      );
    }

    return InteractiveViewer(
      constrained: false,
      boundaryMargin: EdgeInsets.all(100),
      minScale: 0.01,
      maxScale: 5.6,
      child: GraphView(
        graph: graph,
        algorithm: BuchheimWalkerAlgorithm(builder, TreeEdgeRenderer(builder)),
        paint: Paint()
          ..color = Colors.blue
          ..strokeWidth = 1
          ..style = PaintingStyle.stroke,
        builder: (Node node) {
          final nodeId = node.key!.value as String;
          final workflowNode = widget.graph.getNodeById(nodeId);

          if (workflowNode == null) {
            return SizedBox();
          }

          return _buildNodeWidget(workflowNode);
        },
      ),
    );
  }

  Widget _buildNodeWidget(model.WorkflowNode node) {
    return InkWell(
      onTap: () => widget.onNodeTap?.call(node.nodeId),
      child: Container(
        padding: EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _getNodeColor(node.nodeType),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.grey.shade400),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(_getNodeIcon(node.nodeType), size: 32),
            SizedBox(height: 8),
            Text(
              node.name,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 12,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Color _getNodeColor(WorkflowNodeType type) {
    switch (type) {
      case WorkflowNodeType.probe:
        return Colors.blue.shade100;
      case WorkflowNodeType.generator:
        return Colors.green.shade100;
      case WorkflowNodeType.detector:
        return Colors.orange.shade100;
      case WorkflowNodeType.llmResponse:
        return Colors.purple.shade100;
      case WorkflowNodeType.vulnerability:
        return Colors.red.shade100;
    }
  }

  IconData _getNodeIcon(WorkflowNodeType type) {
    switch (type) {
      case WorkflowNodeType.probe:
        return Icons.search;
      case WorkflowNodeType.generator:
        return Icons.settings;
      case WorkflowNodeType.detector:
        return Icons.radar;
      case WorkflowNodeType.llmResponse:
        return Icons.psychology;
      case WorkflowNodeType.vulnerability:
        return Icons.warning;
    }
  }
}
```

### Step 6: Create Workflow Viewer Screen

Create `frontend/lib/screens/workflow/workflow_viewer_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/workflow_provider.dart';
import '../../widgets/workflow/workflow_graph_view.dart';

class WorkflowViewerScreen extends ConsumerStatefulWidget {
  final String scanId;

  const WorkflowViewerScreen({
    Key? key,
    required this.scanId,
  }) : super(key: key);

  @override
  ConsumerState<WorkflowViewerScreen> createState() =>
      _WorkflowViewerScreenState();
}

class _WorkflowViewerScreenState extends ConsumerState<WorkflowViewerScreen> {
  @override
  void initState() {
    super.initState();
    // Load workflow data
    Future.microtask(() {
      ref.read(workflowProvider(widget.scanId).notifier).loadWorkflow();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(workflowProvider(widget.scanId));

    return Scaffold(
      appBar: AppBar(
        title: Text('Workflow Viewer'),
        actions: [
          if (state.graph != null)
            IconButton(
              icon: Icon(Icons.download),
              onPressed: () => _showExportDialog(),
            ),
        ],
      ),
      body: _buildBody(state),
    );
  }

  Widget _buildBody(WorkflowState state) {
    if (state.isLoading) {
      return Center(child: CircularProgressIndicator());
    }

    if (state.error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red),
            SizedBox(height: 16),
            Text('Error loading workflow'),
            Text(state.error!),
            SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                ref.read(workflowProvider(widget.scanId).notifier).loadWorkflow();
              },
              child: Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (state.graph == null) {
      return Center(
        child: Text('No workflow data available'),
      );
    }

    return Column(
      children: [
        // Statistics bar
        Container(
          padding: EdgeInsets.all(16),
          color: Colors.grey.shade100,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildStat('Nodes', state.graph!.nodes.length.toString()),
              _buildStat('Edges', state.graph!.edges.length.toString()),
              _buildStat('Interactions', state.graph!.totalInteractions.toString()),
              _buildStat('Vulnerabilities', state.graph!.vulnerabilitiesFound.toString(),
                  color: state.graph!.hasVulnerabilities ? Colors.red : Colors.green),
            ],
          ),
        ),
        // Graph view
        Expanded(
          child: WorkflowGraphView(
            graph: state.graph!,
            onNodeTap: (nodeId) {
              // Show node details
              _showNodeDetails(nodeId);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildStat(String label, String value, {Color? color}) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(label, style: TextStyle(color: Colors.grey)),
      ],
    );
  }

  void _showNodeDetails(String nodeId) {
    final graph = ref.read(workflowProvider(widget.scanId)).graph;
    final node = graph?.getNodeById(nodeId);

    if (node == null) return;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(node.displayName),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Type: ${node.nodeType.name}'),
            if (node.description != null) Text('Description: ${node.description}'),
            SizedBox(height: 8),
            Text('Metadata:', style: TextStyle(fontWeight: FontWeight.bold)),
            Text(node.metadata.toString()),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showExportDialog() {
    // Implement export dialog
  }
}
```

### Step 7: Add to Enhanced Results Screen

Find `enhanced_results_screen.dart` and add workflow tab:

```dart
// In the TabBar
TabBar(
  tabs: [
    Tab(text: 'Summary'),
    Tab(text: 'Charts'),
    Tab(text: 'Workflow'),  // ADD THIS
    Tab(text: 'Report'),
  ],
)

// In the TabBarView
TabBarView(
  children: [
    _buildSummaryTab(),
    _buildChartsTab(),
    WorkflowViewerScreen(scanId: widget.scanId),  // ADD THIS
    _buildReportTab(),
  ],
)
```

### Step 8: Test with Ollama

1. **Start Backend:**
   ```bash
   cd hydra/backend
   python main.py
   ```

2. **Ensure Ollama is running:**
   ```bash
   ollama list
   ollama pull llama3.1  # if not already pulled
   ```

3. **Run Frontend:**
   ```bash
   cd hydra/frontend
   flutter run -d macos
   ```

4. **Run a Test Scan:**
   - Configure scan with Ollama backend
   - Model: llama3.1
   - Probe: dan.Dan_11_0 or test.Test
   - Start scan
   - Navigate to Results → Workflow tab
   - Verify graph displays

### Step 9: Troubleshooting

**If freezed code generation fails:**
```bash
flutter clean
flutter pub get
flutter pub run build_runner clean
flutter pub run build_runner build --delete-conflicting-outputs
```

**If backend connection fails:**
- Check backend is running on port 8888
- Check CORS settings in backend config
- Verify API base URL in workflow_service.dart

**If graph doesn't display:**
- Check browser console for errors
- Verify workflow data exists: `curl http://localhost:8888/api/v1/scan/{scan_id}/workflow`
- Check that scan completed successfully

---

## Quick Reference

### API Endpoints

```
GET  http://localhost:8888/api/v1/scan/{scan_id}/workflow
GET  http://localhost:8888/api/v1/scan/{scan_id}/workflow/timeline
POST http://localhost:8888/api/v1/scan/{scan_id}/workflow/export
```

### File Locations

**Backend:**
- Models: `backend/models/schemas.py`
- Service: `backend/services/workflow_analyzer.py`
- Routes: `backend/api/routes/workflow.py`
- Integration: `backend/services/garak_wrapper.py`

**Frontend:**
- Models: `frontend/lib/models/workflow/`
- Service: `frontend/lib/services/workflow_service.dart`
- Provider: `frontend/lib/providers/workflow_provider.dart`
- Widget: `frontend/lib/widgets/workflow/workflow_graph_view.dart`
- Screen: `frontend/lib/screens/workflow/workflow_viewer_screen.dart`

---

## Success Criteria

- [ ] Backend API returns workflow data for completed scans
- [ ] Frontend displays workflow graph with nodes and edges
- [ ] Nodes are color-coded by type
- [ ] Clicking nodes shows details
- [ ] Statistics bar shows accurate counts
- [ ] Graph is interactive (zoom, pan)
- [ ] Works with Ollama scans

---

**Created:** 2025-01-19
**Status:** 6/11 tasks complete
**Next:** Complete Steps 1-9 above
