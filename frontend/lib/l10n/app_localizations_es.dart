// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Spanish Castilian (`es`).
class AppLocalizationsEs extends AppLocalizations {
  AppLocalizationsEs([String locale = 'es']) : super(locale);

  @override
  String get appName => 'Hydra';

  @override
  String get appDescription => 'Escáner de Vulnerabilidades LLM';

  @override
  String get appVersion => '1.0.0';

  @override
  String get settings => 'Configuración';

  @override
  String get selectModel => 'Seleccionar Modelo';

  @override
  String get selectProbes => 'Seleccionar Sondas';

  @override
  String get advancedConfiguration => 'Configuración Avanzada';

  @override
  String get browseProbes => 'Explorar Sondas';

  @override
  String get scanExecution => 'Ejecución de Escaneo';

  @override
  String get scanResults => 'Resultados del Escaneo';

  @override
  String get detailedReport => 'Informe Detallado';

  @override
  String get scanHistory => 'Historial de Escaneos';

  @override
  String get myCustomProbes => 'Mis Sondas Personalizadas';

  @override
  String get actions => 'Acciones';

  @override
  String get scan => 'Escanear';

  @override
  String get startNewScan => 'Iniciar nuevo escaneo';

  @override
  String get browseProbesAction => 'Explorar Sondas';

  @override
  String get viewAllTests => 'Ver todas las pruebas';

  @override
  String get writeProbe => 'Escribir Sonda';

  @override
  String get createCustomProbe => 'Crear sonda personalizada';

  @override
  String get myProbes => 'Mis Sondas';

  @override
  String get manageSavedProbes => 'Gestionar sondas guardadas';

  @override
  String get history => 'Historial';

  @override
  String get pastScans => 'Escaneos anteriores';

  @override
  String get recentScans => 'Escaneos Recientes';

  @override
  String get viewAll => 'Ver Todo';

  @override
  String get llmVulnerabilityScanner => 'Escáner de Vulnerabilidades LLM';

  @override
  String get scanDescription =>
      'Escanea tus modelos de lenguaje en busca de vulnerabilidades incluyendo jailbreaks, inyección de prompts, toxicidad y más.';

  @override
  String get poweredByGarak => 'Impulsado por Garak';

  @override
  String get cancel => 'Cancelar';

  @override
  String get reset => 'Restablecer';

  @override
  String get testConnection => 'Probar Conexión';

  @override
  String get resetToDefaults => 'Restablecer Valores';

  @override
  String get saveSettings => 'Guardar Configuración';

  @override
  String get continueToProbeSelection => 'Continuar a Selección de Sondas';

  @override
  String get clear => 'Limpiar';

  @override
  String get advanced => 'Avanzado';

  @override
  String get quickStart => 'Inicio Rápido';

  @override
  String get goBack => 'Volver';

  @override
  String get cancelScan => 'Cancelar Escaneo';

  @override
  String get viewResults => 'Ver Resultados';

  @override
  String get retry => 'Reintentar';

  @override
  String get backToHome => 'Volver al Inicio';

  @override
  String get newProbe => 'Nueva Sonda';

  @override
  String get validate => 'Validar';

  @override
  String get gotIt => 'Entendido';

  @override
  String get delete => 'Eliminar';

  @override
  String get no => 'No';

  @override
  String get yesCancelScan => 'Sí, Cancelar';

  @override
  String get stay => 'Quedarse';

  @override
  String get ok => 'Aceptar';

  @override
  String get resetSettings => 'Restablecer Configuración';

  @override
  String get resetSettingsConfirm =>
      '¿Restablecer toda la configuración a los valores predeterminados?';

  @override
  String get connectionTroubleshooting => 'Solución de Problemas de Conexión';

  @override
  String get apiKeyInformation => 'Información de Clave API';

  @override
  String get apiKeyInfoContent =>
      'La clave API es opcional aquí. Si ya has configurado la clave API como variable de entorno en tu sistema, no necesitas ingresarla de nuevo. Este campo solo es necesario si deseas sobrescribir la variable de entorno.';

  @override
  String get aboutProbes => 'Acerca de las Sondas';

  @override
  String get aboutProbesContent =>
      'Las sondas son módulos de prueba que verifican vulnerabilidades específicas en modelos de lenguaje. Cada sonda contiene múltiples prompts diseñados para evaluar qué tan bien el modelo maneja entradas potencialmente dañinas.';

  @override
  String get cancelScanConfirm =>
      '¿Estás seguro de que deseas cancelar este escaneo?';

  @override
  String get scanInProgress => 'Escaneo en Progreso';

  @override
  String get scanInProgressContent =>
      'Hay un escaneo en ejecución. ¿Deseas cancelarlo?';

  @override
  String get exportSuccessful => 'Exportación Exitosa';

  @override
  String get detailedScanReport => 'Informe Detallado del Escaneo';

  @override
  String get deleteProbe => 'Eliminar Sonda';

  @override
  String get deleteProbeConfirm =>
      '¿Estás seguro de que deseas eliminar esta sonda? Esta acción no se puede deshacer.';

  @override
  String get apiBaseUrl => 'URL Base de API';

  @override
  String get apiBaseUrlHint => 'http://localhost:8888/api/v1';

  @override
  String get apiBaseUrlDescription =>
      'Endpoint de API del backend para operaciones de escaneo';

  @override
  String get generatorType => 'Tipo de Generador';

  @override
  String get modelName => 'Nombre del Modelo';

  @override
  String get modelNameDescription =>
      'Ingresa el identificador específico del modelo';

  @override
  String get apiKey => 'Clave API';

  @override
  String get apiKeyDescription =>
      'Opcional: Sobrescribir clave API de variable de entorno';

  @override
  String get apiKeyHint => 'sk-...';

  @override
  String get parallelRequests => 'Solicitudes Paralelas';

  @override
  String get parallelRequestsHint => 'ej., 5';

  @override
  String get parallelAttempts => 'Intentos Paralelos';

  @override
  String get parallelAttemptsHint => 'ej., 3';

  @override
  String get randomSeed => 'Semilla Aleatoria';

  @override
  String get randomSeedHint => 'ej., 42';

  @override
  String get searchProbes => 'Buscar sondas...';

  @override
  String get probeName => 'Nombre de Sonda';

  @override
  String get probeNameHint => 'MiSondaPersonalizada';

  @override
  String get descriptionOptional => 'Descripción (opcional)';

  @override
  String get descriptionHint => 'Breve descripción de lo que prueba esta sonda';

  @override
  String get probeCodeHint => '# Escribe tu código de sonda aquí...';

  @override
  String get searchScans => 'Buscar escaneos...';

  @override
  String get connectionError =>
      'No se puede conectar al servidor. Asegúrate de que el backend esté en ejecución.';

  @override
  String get networkError => 'Error de red. Por favor verifica tu conexión.';

  @override
  String get timeoutError =>
      'Tiempo de espera agotado. El servidor puede estar lento o no disponible.';

  @override
  String get authError =>
      'Falló la autenticación. Por favor verifica tu clave API.';

  @override
  String get forbiddenError =>
      'Acceso denegado. Es posible que no tengas permiso para esta acción.';

  @override
  String get notFoundError =>
      'Recurso no encontrado. Puede haber sido eliminado.';

  @override
  String get serverError =>
      'Error del servidor. Por favor intenta de nuevo más tarde.';

  @override
  String get noScansFound =>
      'No se encontraron escaneos. Completa un escaneo para ver el historial.';

  @override
  String get settingsSaved => 'Configuración guardada exitosamente';

  @override
  String get settingsReset =>
      'Configuración restablecida a valores predeterminados';

  @override
  String get connectionSuccessful => '¡Conexión al backend exitosa!';

  @override
  String get testingConnection => 'Probando conexión...';

  @override
  String get selectGeneratorAndModel =>
      'Por favor selecciona un tipo de generador e ingresa un nombre de modelo';

  @override
  String get selectAtLeastOneProbe =>
      'Por favor selecciona al menos una sonda o selecciona todas';

  @override
  String get enterProbeName => 'Por favor ingresa un nombre de sonda';

  @override
  String get enterProbeCode => 'Por favor ingresa código de sonda';

  @override
  String get fixValidationErrors =>
      'Por favor corrige los errores de validación antes de guardar';

  @override
  String get probeCreatedSuccess => '¡Sonda guardada exitosamente!';

  @override
  String get startingScan => 'Iniciando escaneo...';

  @override
  String get darkMode => 'Modo Oscuro';

  @override
  String get useDarkTheme => 'Usar tema oscuro';

  @override
  String get version => 'Versión';

  @override
  String get description => 'Descripción';

  @override
  String get garakLlmScanner => 'Escáner LLM Garak';

  @override
  String get testingLlmsVulnerabilities =>
      'Probando LLMs para vulnerabilidades';

  @override
  String get openSource => 'Código Abierto';

  @override
  String get apacheLicense => 'Licencia Apache 2.0';

  @override
  String get connectionGuide => 'Guía de Conexión';

  @override
  String get forAndroidEmulator => 'Para Emulador Android:';

  @override
  String get useAndroidEmulatorUrl => 'Usa http://10.0.2.2:8888/api/v1';

  @override
  String get forIosSimulator => 'Para Simulador iOS:';

  @override
  String get useLocalhostUrl => 'Usa http://localhost:8888/api/v1';

  @override
  String get forDesktopWeb => 'Para Escritorio/Web:';

  @override
  String get useDesktopUrl =>
      'Usa http://localhost:8888/api/v1 o http://127.0.0.1:8888/api/v1';

  @override
  String get selectAllProbes => 'Seleccionar Todas las Sondas';

  @override
  String get runComprehensiveScan => 'Ejecutar escaneo completo';

  @override
  String get allCategories => 'Todas las Categorías';

  @override
  String get inactive => 'Inactivo';

  @override
  String get active => 'Activo';

  @override
  String get fullName => 'Nombre Completo';

  @override
  String get status => 'Estado';

  @override
  String get tags => 'Etiquetas';

  @override
  String get fastScan => 'Escaneo Rápido';

  @override
  String get fastScanDescription => 'Escaneo rápido con sondas esenciales';

  @override
  String get defaultScan => 'Escaneo Predeterminado';

  @override
  String get defaultScanDescription =>
      'Escaneo equilibrado que cubre vulnerabilidades comunes';

  @override
  String get fullScan => 'Escaneo Completo';

  @override
  String get fullScanDescription => 'Escaneo exhaustivo con máxima rigurosidad';

  @override
  String get owaspLlmTop10 => 'OWASP LLM Top 10';

  @override
  String get owaspLlmTop10Description =>
      'Enfoque en vulnerabilidades OWASP LLM Top 10';

  @override
  String get openai => 'OpenAI';

  @override
  String get huggingFace => 'Hugging Face';

  @override
  String get replicate => 'Replicate';

  @override
  String get cohere => 'Cohere';

  @override
  String get anthropic => 'Anthropic';

  @override
  String get litellm => 'LiteLLM';

  @override
  String get nvidiaNim => 'NVIDIA NIM';

  @override
  String get ollama => 'Ollama';

  @override
  String get ollamaSetup => 'Configuración de Ollama';

  @override
  String get ollamaInstructions =>
      'Asegúrate de que Ollama esté ejecutándose localmente. Por defecto, se ejecuta en el puerto 11434.';

  @override
  String get popularModels =>
      'Modelos populares: llama2, llama3, gemma, mistral, codellama';

  @override
  String get quickPresets => 'Preajustes Rápidos';

  @override
  String get startWithPreset =>
      'Comenzar con una configuración preestablecida (opcional)';

  @override
  String get configureTargetModel => 'Configurar Modelo Objetivo';

  @override
  String get selectLlmGenerator =>
      'Selecciona el generador LLM y modelo que deseas probar';

  @override
  String get passRate => 'Tasa de Aprobación';

  @override
  String get totalTests => 'Total de Pruebas';

  @override
  String get shareResults => 'Compartir Resultados';

  @override
  String get export => 'Exportar';

  @override
  String get exportAsJson => 'Exportar como JSON';

  @override
  String get exportAsHtml => 'Exportar como HTML';

  @override
  String get exportAsPdf => 'Exportar como PDF';

  @override
  String get errorLoadingResults => 'Error al Cargar Resultados';

  @override
  String get failedToLoadProbes => 'Error al cargar sondas';

  @override
  String get noScanHistory => 'Sin historial de escaneos';

  @override
  String get sortByDate => 'Ordenar por Fecha';

  @override
  String get sortByStatus => 'Ordenar por Estado';

  @override
  String get sortByName => 'Ordenar por Nombre';

  @override
  String get refresh => 'Actualizar';

  @override
  String get failedToLoadScanHistory => 'Error al cargar historial de escaneos';

  @override
  String get noScanHistoryMessage => 'Tus escaneos completados aparecerán aquí';

  @override
  String get about => 'Acerca de';

  @override
  String get parallelRequestsTooltip =>
      'Número de solicitudes concurrentes al modelo objetivo';

  @override
  String get parallelAttemptsTooltip =>
      'Número de reintentos para solicitudes fallidas';

  @override
  String get generationsPerPrompt => 'Generaciones por Prompt';

  @override
  String get generationsPerPromptTooltip =>
      'Número de prompts de prueba a generar por sonda';

  @override
  String get evaluationThreshold => 'Umbral de Evaluación';

  @override
  String get evaluationThresholdTooltip =>
      'Umbral de evaluación para marcar pruebas como fallidas (0.0 a 1.0)';

  @override
  String get modelHintOpenai => 'gpt-4, gpt-3.5-turbo, etc.';

  @override
  String get modelHintHuggingface => 'meta-llama/Llama-2-7b-chat-hf, etc.';

  @override
  String get modelHintReplicate => 'meta/llama-2-70b-chat, etc.';

  @override
  String get modelHintCohere => 'command, command-light, etc.';

  @override
  String get modelHintAnthropic => 'claude-3-opus-20240229, etc.';

  @override
  String get modelHintLitellm => 'gpt-4, claude-2, etc.';

  @override
  String get modelHintNim => 'meta/llama3-70b-instruct, etc.';

  @override
  String get modelHintOllama => 'llama2, mistral, codellama, etc.';

  @override
  String get probeResults => 'Resultados de Sondas';

  @override
  String get passed => 'Aprobado';

  @override
  String get failed => 'Fallido';

  @override
  String get total => 'Total';

  @override
  String get details => 'Detalles';

  @override
  String get summary => 'Resumen';

  @override
  String get configuration => 'Configuración';

  @override
  String get model => 'Modelo';

  @override
  String get generator => 'Generador';

  @override
  String get probesSelected => 'Sondas Seleccionadas';

  @override
  String get startTime => 'Hora de Inicio';

  @override
  String get endTime => 'Hora de Fin';

  @override
  String get duration => 'Duración';

  @override
  String get connectionFailed => 'Conexión fallida';

  @override
  String get checkBackendRunning =>
      'Por favor verifica si el servidor backend está en ejecución';

  @override
  String get language => 'Idioma';

  @override
  String get selectLanguage => 'Seleccionar Idioma';

  @override
  String get english => 'Inglés';

  @override
  String get korean => 'Coreano';

  @override
  String get japanese => 'Japonés';

  @override
  String get spanish => 'Español';

  @override
  String get chinese => 'Chino';

  @override
  String get apiConfiguration => 'Configuración de API';

  @override
  String get appearance => 'Apariencia';

  @override
  String get defaultScanSettings => 'Configuración de Escaneo Predeterminada';

  @override
  String get advancedSettings => 'Configuración Avanzada';

  @override
  String get generations => 'Generaciones';

  @override
  String get generationsTooltip =>
      'Número de prompts de prueba a generar por sonda. Valores más altos = pruebas más exhaustivas.';

  @override
  String get threshold => 'Umbral';

  @override
  String get thresholdTooltip =>
      'Umbral de evaluación para marcar pruebas como fallidas. Valores más bajos = detección más estricta.';

  @override
  String get connectionTimeout => 'Tiempo de Conexión';

  @override
  String get connectionTimeoutTooltip =>
      'Tiempo de espera para establecer conexión con el backend.';

  @override
  String get receiveTimeout => 'Tiempo de Recepción';

  @override
  String get receiveTimeoutTooltip =>
      'Tiempo de espera para respuesta del backend. Aumente para redes lentas o respuestas LLM grandes.';

  @override
  String get wsReconnectDelay => 'Retraso de Reconexión WS';

  @override
  String get wsReconnectDelayTooltip =>
      'Retraso antes de intentar reconectar WebSocket después de desconexión.';

  @override
  String get targetEndpoint => 'Endpoint de Destino';

  @override
  String get targetEndpointTooltip =>
      'URL del endpoint del servicio LLM de destino.';

  @override
  String get restartForSettings =>
      'Reinicie la aplicación para que la configuración de red surta efecto.';
}
