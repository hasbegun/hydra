# Hydra

A modern cross platform GUI for [Garak](https://github.com/leondz/garak), NVIDIA's LLM vulnerability scanner. Hydra provides an intuitive interface to scan language models for security vulnerabilities including jailbreaks, prompt injection, toxicity, and more.

## Project Structure

```
hydra/
├── backend/          # FastAPI backend service
│   ├── api/          # API routes
│   ├── models/       # Data models
│   ├── services/     # Business logic
│   ├── config/       # Configuration
│   └── main.py       # Entry point
├── frontend/         # Flutter desktop application
│   ├── lib/          # Dart source code
│   ├── assets/       # Images, fonts, etc.
│   └── pubspec.yaml  # Flutter dependencies
└── README.md         # This file
```

## Features

- **Quick Scan**: Fast vulnerability scanning with preset configurations
- **Full Scan**: Comprehensive testing with all available probes
- **Browse Probes**: Explore all available vulnerability probes
- **Scan History**: View and analyze past scan results
- **Real-time Progress**: WebSocket-based live scan monitoring
- **Rich Results**: Interactive HTML reports with detailed breakdowns

## Prerequisites

- **Python 3.8+** (for backend)
- **Flutter 3.0+** (for frontend)
- **Garak** (LLM vulnerability scanner)
- **Ollama/OpenAI/Anthropic** (or other supported LLM providers)

## Installation

### 1. Install Garak

```bash
pip install garak
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
flutter pub get
```

## Running the Application

### Start the Backend

```bash
cd backend
python main.py
```

The backend will start on `http://localhost:8888`

### Start the Frontend

```bash
cd frontend
flutter run -d macos  # Or: -d windows, -d linux
```

## Configuration

### Backend Configuration

Create a `.env` file in the `backend` directory:

```env
# Server settings
HOST=0.0.0.0
PORT=8888
LOG_LEVEL=INFO

# Optional: Custom garak path
GARAK_PATH=/path/to/garak

# Optional: API keys for LLM providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Frontend Configuration

The frontend automatically connects to `http://localhost:8888`. To change this, edit:

```dart
// frontend/lib/config/constants.dart
class ApiConstants {
  static const String baseUrl = 'http://localhost:8888';
}
```

## Development

### Backend Development

```bash
cd backend
# Run with auto-reload
python main.py

# Run tests
pytest tests/

# Format code
black .
```

### Frontend Development

```bash
cd frontend
# Hot reload is enabled by default
flutter run -d macos

# Generate code (if using code generation)
flutter pub run build_runner build --delete-conflicting-outputs

# Run tests
flutter test
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8888/docs`
- ReDoc: `http://localhost:8888/redoc`

## Scan Workflow

1. **Select Model**: Choose your LLM provider and model
2. **Configure Probes**: Select vulnerability tests to run
3. **Start Scan**: Initiate the scan with real-time progress
4. **View Results**: Analyze detailed HTML reports
5. **History**: Access past scans anytime

## Keyboard Shortcuts

Hydra supports keyboard shortcuts for common actions. On macOS, use `⌘` (Command); on Windows/Linux, use `Ctrl`.

| Shortcut | Action | Available On |
|----------|--------|--------------|
| `⌘/Ctrl + N` | New Scan | Home Screen |
| `⌘/Ctrl + ,` | Open Settings | Home Screen |
| `⌘/Ctrl + H` | Open Scan History | Home Screen |
| `⌘/Ctrl + S` | Save Settings | Settings Screen |
| `⌘/Ctrl + Enter` | Start Scan | Advanced Config Screen |
| `⌘/Ctrl + E` | Export Configuration | Advanced Config Screen |
| `⌘/Ctrl + F` | Search | Screens with search |
| `Escape` | Go Back / Cancel | All Screens |

### Shortcut Hints

Keyboard shortcuts are displayed in tooltips throughout the UI. Hover over buttons and action cards to see available shortcuts.

## Supported LLM Providers

- OpenAI (GPT-3.5, GPT-4, etc.)
- Anthropic (Claude)
- Ollama (Local models)
- HuggingFace
- Cohere
- Replicate
- LiteLLM
- NVIDIA NIM

## Architecture

### Backend (FastAPI)

- **RESTful API**: Standard HTTP endpoints for all operations
- **WebSocket**: Real-time scan progress updates
- **Async Processing**: Non-blocking scan execution
- **File System**: Reads historical scans from garak's output directory

### Frontend (Flutter)

- **Riverpod**: State management
- **Dio**: HTTP client with interceptors
- **WebSocket**: Real-time progress monitoring
- **Material 3**: Modern dark theme UI

## Troubleshooting

### Backend Issues

**Port already in use:**
```bash
lsof -ti:8888 | xargs kill -9
```

**Garak not found:**
```bash
which garak
# Or set GARAK_PATH in .env
```

### Frontend Issues

**Build errors:**
```bash
flutter clean
flutter pub get
flutter pub run build_runner build --delete-conflicting-outputs
```

## Screenshots

### Home Screen
The main dashboard provides quick access to all key features:

![Home Screen](screenshots/main1.png)

### Model Configuration
Select your target model from multiple LLM providers with built-in presets:

![Model Selection](screenshots/scan1.png)

### Probe Selection
Browse and select from hundreds of vulnerability probes organized by category:

![Probe Selection](screenshots/probe1.png)

### Scan Execution
Real-time progress tracking with detailed status information:

![Scan Execution](screenshots/scan_exe1.png)

### Scan History
View all past scans with pass/fail metrics at a glance:

![Scan History](screenshots/history.png)

### Detailed Results
Comprehensive results with visualizations and metrics:

![Results Detail](screenshots/report_detail.png)


## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is a GUI wrapper for Garak. Please refer to [Garak's license](https://github.com/leondz/garak) for the underlying scanner.

## Acknowledgments

- [Garak](https://github.com/leondz/garak) by NVIDIA for the core vulnerability scanner
- Flutter and FastAPI communities for excellent frameworks
