# Hydra

A Flutter GUI application for the [garak](https://github.com/NVIDIA/garak) LLM vulnerability scanner.

## Overview

Hydra provides a modern, cross-platform graphical interface for running garak vulnerability scans against large language models. Test your LLMs for:

- 🛡️ Jailbreaks (DAN attacks, etc.)
- 💉 Prompt Injection
- 🔥 Toxicity & Hate Speech
- 📊 OWASP LLM Top 10 vulnerabilities
- 📡 Data Leakage
- And more...

## Screenshots

### Home Screen
The main dashboard provides quick access to all key features:

![Home Screen](../screens/main1.png)

### Model Configuration
Select your target model from multiple LLM providers with built-in presets:

![Model Selection](../screens/scan1.png)

### Probe Selection
Browse and select from hundreds of vulnerability probes organized by category:

![Probe Selection](../screens/probe1.png)

### Scan Execution
Real-time progress tracking with detailed status information:

![Scan Execution](../screens/scan_exe1.png)

### Scan History
View all past scans with pass/fail metrics at a glance:

![Scan History](../screens/history.png)

### Detailed Results
Comprehensive results with visualizations and metrics:

![Results Detail](../screens/report_detail.png)

## Prerequisites

1. **Flutter SDK** (3.9.0 or higher)
   ```bash
   flutter --version
   ```

2. **Garak Backend** (running)
   - See `../garak_backend/README.md` for setup instructions

3. **Garak CLI** installed (required by backend)
   ```bash
   pip install garak
   ```

## Getting Started

### 1. Install Dependencies

```bash
cd hydra/frontend
flutter pub get
```

### 2. Generate Code

The project uses code generation for JSON serialization. Run:

```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

### 3. Configure Backend URL

Edit `lib/config/constants.dart` if your backend is not running on `localhost:8888`:

```dart
static const String apiBaseUrl = 'http://localhost:8888/api/v1';
static const String wsBaseUrl = 'ws://localhost:8888/api/v1';
```

### 4. Run the App

```bash
# Desktop (macOS, Linux, Windows)
flutter run -d macos    # or linux, windows

# Web
flutter run -d chrome

# Mobile (requires emulator/device)
flutter run -d ios      # or android
```

## Project Structure

```
lib/
├── main.dart                    # App entry point
├── config/
│   └── constants.dart          # App constants & configuration
├── models/                      # Data models
│   ├── scan_config.dart        # Scan configuration
│   ├── scan_status.dart        # Scan status & response
│   ├── plugin.dart             # Plugin information
│   └── system_info.dart        # System information
├── services/                    # Backend communication
│   ├── api_service.dart        # REST API client
│   └── websocket_service.dart  # WebSocket for real-time updates
├── providers/                   # State management (Riverpod)
├── screens/                     # UI screens
│   ├── home/                   # Home screen
│   ├── configuration/          # Scan configuration
│   ├── scan/                   # Scan execution
│   ├── results/                # Results viewing
│   └── settings/               # Settings
└── widgets/                     # Reusable widgets
    ├── common/                 # Common widgets
    ├── config/                 # Configuration widgets
    ├── scan/                   # Scan widgets
    └── results/                # Results widgets
```

## Features (Roadmap)

### ✅ Phase 1 - MVP (In Progress)
- [x] Project setup
- [x] API service layer
- [x] Data models
- [x] Basic home screen
- [ ] Model selection UI
- [ ] Probe selection UI
- [ ] Start scan functionality
- [ ] Progress display
- [ ] Basic results view

### 📋 Phase 2 - Enhanced Features
- [ ] Advanced probe filters
- [ ] Detector configuration
- [ ] Configuration presets
- [ ] YAML import/export
- [ ] Detailed results dashboard
- [ ] Visualizations (charts)
- [ ] Report export (HTML, AVID)
- [ ] Scan history

### 🚀 Phase 3 - Advanced
- [ ] Dark mode toggle
- [ ] Multi-platform optimization
- [ ] Scheduled scans
- [ ] Comparison tools
- [ ] Custom probe creation

## Development

### Hot Reload

While the app is running, press `r` for hot reload or `R` for hot restart.

### Code Generation

When you modify model classes with `@JsonSerializable()`, regenerate code:

```bash
flutter pub run build_runner watch
```

This watches for changes and auto-generates code.

### Debugging

```bash
# Run with verbose logging
flutter run -v

# Debug mode
flutter run --debug
```

### Building

```bash
# Web
flutter build web

# Desktop
flutter build macos    # or linux, windows

# Mobile
flutter build apk      # Android
flutter build ios      # iOS (requires macOS)
```

## Configuration

### API Keys

For security, API keys should be stored securely:

1. The app uses `flutter_secure_storage` for sensitive data
2. API keys are passed to the backend via `generator_options`
3. Never commit API keys to version control

### Presets

The app includes built-in presets:
- **Fast**: Quick scan with parallel execution
- **Default**: Balanced scan
- **Full**: Comprehensive testing
- **OWASP**: OWASP LLM Top 10 focused

## Troubleshooting

### Backend Connection Failed

1. Ensure garak_backend is running:
   ```bash
   cd ../garak_backend
   python main.py
   ```

2. Check the backend URL in `lib/config/constants.dart`

3. Verify backend health:
   ```bash
   curl http://localhost:8888/health
   ```

### Build Errors

1. Clean and rebuild:
   ```bash
   flutter clean
   flutter pub get
   flutter pub run build_runner build --delete-conflicting-outputs
   ```

2. Check Flutter version:
   ```bash
   flutter doctor
   ```

### WebSocket Issues

- WebSocket connections may fail in some network environments
- Check firewall/proxy settings
- Fallback to polling (status checks) is automatic

## Contributing

This is part of a larger garak ecosystem. For contributions:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

Same as garak - Apache 2.0

## Resources

- [Garak Documentation](https://reference.garak.ai/)
- [Flutter Documentation](https://docs.flutter.dev/)
- [Riverpod Documentation](https://riverpod.dev/)

## Support

For issues or questions:
- Check the garak documentation
- Review existing issues
- Create a new issue with details
