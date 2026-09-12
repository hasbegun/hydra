// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Korean (`ko`).
class AppLocalizationsKo extends AppLocalizations {
  AppLocalizationsKo([String locale = 'ko']) : super(locale);

  @override
  String get appName => 'Hydra';

  @override
  String get appDescription => 'LLM 취약점 스캐너';

  @override
  String get appVersion => '1.0.0';

  @override
  String get settings => '설정';

  @override
  String get selectModel => '모델 선택';

  @override
  String get selectProbes => '프로브 선택';

  @override
  String get advancedConfiguration => '고급 설정';

  @override
  String get browseProbes => '프로브 탐색';

  @override
  String get scanExecution => '스캔 실행';

  @override
  String get scanResults => '스캔 결과';

  @override
  String get detailedReport => '상세 보고서';

  @override
  String get scanHistory => '스캔 기록';

  @override
  String get myCustomProbes => '내 커스텀 프로브';

  @override
  String get actions => '작업';

  @override
  String get scan => '스캔';

  @override
  String get startNewScan => '새 스캔 시작';

  @override
  String get browseProbesAction => '프로브 탐색';

  @override
  String get viewAllTests => '모든 테스트 보기';

  @override
  String get writeProbe => '프로브 작성';

  @override
  String get createCustomProbe => '커스텀 프로브 생성';

  @override
  String get myProbes => '내 프로브';

  @override
  String get manageSavedProbes => '저장된 프로브 관리';

  @override
  String get history => '기록';

  @override
  String get pastScans => '이전 스캔';

  @override
  String get recentScans => '최근 스캔';

  @override
  String get viewAll => '모두 보기';

  @override
  String get llmVulnerabilityScanner => 'LLM 취약점 스캐너';

  @override
  String get scanDescription => '탈옥, 프롬프트 인젝션, 독성 등 언어 모델의 취약점을 스캔합니다.';

  @override
  String get poweredByGarak => 'Garak 기반';

  @override
  String get cancel => '취소';

  @override
  String get reset => '초기화';

  @override
  String get testConnection => '연결 테스트';

  @override
  String get resetToDefaults => '기본값으로 초기화';

  @override
  String get saveSettings => '설정 저장';

  @override
  String get continueToProbeSelection => '프로브 선택으로 계속';

  @override
  String get clear => '지우기';

  @override
  String get advanced => '고급';

  @override
  String get quickStart => '빠른 시작';

  @override
  String get goBack => '뒤로 가기';

  @override
  String get cancelScan => '스캔 취소';

  @override
  String get viewResults => '결과 보기';

  @override
  String get retry => '재시도';

  @override
  String get backToHome => '홈으로 돌아가기';

  @override
  String get newProbe => '새 프로브';

  @override
  String get validate => '검증';

  @override
  String get gotIt => '확인';

  @override
  String get delete => '삭제';

  @override
  String get no => '아니오';

  @override
  String get yesCancelScan => '예, 취소';

  @override
  String get stay => '유지';

  @override
  String get ok => '확인';

  @override
  String get resetSettings => '설정 초기화';

  @override
  String get resetSettingsConfirm => '모든 설정을 기본값으로 초기화하시겠습니까?';

  @override
  String get connectionTroubleshooting => '연결 문제 해결';

  @override
  String get apiKeyInformation => 'API 키 정보';

  @override
  String get apiKeyInfoContent =>
      'API 키는 선택 사항입니다. 시스템에 환경 변수로 API 키를 이미 설정한 경우 다시 입력할 필요가 없습니다. 이 필드는 환경 변수를 재정의하려는 경우에만 필요합니다.';

  @override
  String get aboutProbes => '프로브 정보';

  @override
  String get aboutProbesContent =>
      '프로브는 언어 모델의 특정 취약점을 검사하는 테스트 모듈입니다. 각 프로브에는 모델이 잠재적으로 유해한 입력을 얼마나 잘 처리하는지 평가하기 위한 여러 프롬프트가 포함되어 있습니다.';

  @override
  String get cancelScanConfirm => '이 스캔을 취소하시겠습니까?';

  @override
  String get scanInProgress => '스캔 진행 중';

  @override
  String get scanInProgressContent => '현재 스캔이 실행 중입니다. 취소하시겠습니까?';

  @override
  String get exportSuccessful => '내보내기 성공';

  @override
  String get detailedScanReport => '상세 스캔 보고서';

  @override
  String get deleteProbe => '프로브 삭제';

  @override
  String get deleteProbeConfirm => '이 프로브를 삭제하시겠습니까? 이 작업은 취소할 수 없습니다.';

  @override
  String get apiBaseUrl => 'API 기본 URL';

  @override
  String get apiBaseUrlHint => 'http://localhost:8888/api/v1';

  @override
  String get apiBaseUrlDescription => '스캔 작업을 위한 백엔드 API 엔드포인트';

  @override
  String get generatorType => '생성기 유형';

  @override
  String get modelName => '모델 이름';

  @override
  String get modelNameDescription => '특정 모델 식별자를 입력하세요';

  @override
  String get apiKey => 'API 키';

  @override
  String get apiKeyDescription => '선택 사항: 환경 변수 API 키 재정의';

  @override
  String get apiKeyHint => 'sk-...';

  @override
  String get parallelRequests => '병렬 요청';

  @override
  String get parallelRequestsHint => '예: 5';

  @override
  String get parallelAttempts => '병렬 시도';

  @override
  String get parallelAttemptsHint => '예: 3';

  @override
  String get randomSeed => '랜덤 시드';

  @override
  String get randomSeedHint => '예: 42';

  @override
  String get searchProbes => '프로브 검색...';

  @override
  String get probeName => '프로브 이름';

  @override
  String get probeNameHint => 'MyCustomProbe';

  @override
  String get descriptionOptional => '설명 (선택 사항)';

  @override
  String get descriptionHint => '이 프로브가 테스트하는 내용에 대한 간략한 설명';

  @override
  String get probeCodeHint => '# 여기에 프로브 코드를 작성하세요...';

  @override
  String get searchScans => '스캔 검색...';

  @override
  String get connectionError => '서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.';

  @override
  String get networkError => '네트워크 오류입니다. 연결을 확인하세요.';

  @override
  String get timeoutError => '요청 시간이 초과되었습니다. 서버가 느리거나 사용할 수 없을 수 있습니다.';

  @override
  String get authError => '인증에 실패했습니다. API 키를 확인하세요.';

  @override
  String get forbiddenError => '액세스가 거부되었습니다. 이 작업에 대한 권한이 없을 수 있습니다.';

  @override
  String get notFoundError => '리소스를 찾을 수 없습니다. 삭제되었을 수 있습니다.';

  @override
  String get serverError => '서버 오류입니다. 나중에 다시 시도하세요.';

  @override
  String get noScansFound => '스캔을 찾을 수 없습니다. 스캔을 완료하면 기록을 볼 수 있습니다.';

  @override
  String get settingsSaved => '설정이 성공적으로 저장되었습니다';

  @override
  String get settingsReset => '설정이 기본값으로 초기화되었습니다';

  @override
  String get connectionSuccessful => '백엔드 연결 성공!';

  @override
  String get testingConnection => '연결 테스트 중...';

  @override
  String get selectGeneratorAndModel => '생성기 유형을 선택하고 모델 이름을 입력하세요';

  @override
  String get selectAtLeastOneProbe => '최소 하나의 프로브를 선택하거나 모두 선택하세요';

  @override
  String get enterProbeName => '프로브 이름을 입력하세요';

  @override
  String get enterProbeCode => '프로브 코드를 입력하세요';

  @override
  String get fixValidationErrors => '저장하기 전에 검증 오류를 수정하세요';

  @override
  String get probeCreatedSuccess => '프로브가 성공적으로 저장되었습니다!';

  @override
  String get startingScan => '스캔 시작 중...';

  @override
  String get darkMode => '다크 모드';

  @override
  String get useDarkTheme => '다크 테마 사용';

  @override
  String get version => '버전';

  @override
  String get description => '설명';

  @override
  String get garakLlmScanner => 'Garak LLM 스캐너';

  @override
  String get testingLlmsVulnerabilities => 'LLM 취약점 테스트';

  @override
  String get openSource => '오픈 소스';

  @override
  String get apacheLicense => 'Apache 2.0 라이선스';

  @override
  String get connectionGuide => '연결 가이드';

  @override
  String get forAndroidEmulator => 'Android 에뮬레이터:';

  @override
  String get useAndroidEmulatorUrl => 'http://10.0.2.2:8888/api/v1 사용';

  @override
  String get forIosSimulator => 'iOS 시뮬레이터:';

  @override
  String get useLocalhostUrl => 'http://localhost:8888/api/v1 사용';

  @override
  String get forDesktopWeb => '데스크톱/웹:';

  @override
  String get useDesktopUrl =>
      'http://localhost:8888/api/v1 또는 http://127.0.0.1:8888/api/v1 사용';

  @override
  String get selectAllProbes => '모든 프로브 선택';

  @override
  String get runComprehensiveScan => '종합 스캔 실행';

  @override
  String get allCategories => '모든 카테고리';

  @override
  String get inactive => '비활성';

  @override
  String get active => '활성';

  @override
  String get fullName => '전체 이름';

  @override
  String get status => '상태';

  @override
  String get tags => '태그';

  @override
  String get fastScan => '빠른 스캔';

  @override
  String get fastScanDescription => '필수 프로브로 빠른 스캔';

  @override
  String get defaultScan => '기본 스캔';

  @override
  String get defaultScanDescription => '일반적인 취약점을 포괄하는 균형 잡힌 스캔';

  @override
  String get fullScan => '전체 스캔';

  @override
  String get fullScanDescription => '최대 철저함을 갖춘 종합 스캔';

  @override
  String get owaspLlmTop10 => 'OWASP LLM Top 10';

  @override
  String get owaspLlmTop10Description => 'OWASP LLM Top 10 취약점에 집중';

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
  String get ollamaSetup => 'Ollama 설정';

  @override
  String get ollamaInstructions =>
      'Ollama가 로컬에서 실행 중인지 확인하세요. 기본적으로 포트 11434에서 실행됩니다.';

  @override
  String get popularModels =>
      '인기 모델: llama2, llama3, gemma, mistral, codellama';

  @override
  String get quickPresets => '빠른 프리셋';

  @override
  String get startWithPreset => '프리셋 구성으로 시작 (선택 사항)';

  @override
  String get configureTargetModel => '대상 모델 구성';

  @override
  String get selectLlmGenerator => '테스트할 LLM 생성기와 모델을 선택하세요';

  @override
  String get passRate => '통과율';

  @override
  String get totalTests => '총 테스트';

  @override
  String get shareResults => '결과 공유';

  @override
  String get export => '내보내기';

  @override
  String get exportAsJson => 'JSON으로 내보내기';

  @override
  String get exportAsHtml => 'HTML로 내보내기';

  @override
  String get exportAsPdf => 'PDF로 내보내기';

  @override
  String get errorLoadingResults => '결과 로딩 오류';

  @override
  String get failedToLoadProbes => '프로브 로딩 실패';

  @override
  String get noScanHistory => '스캔 기록 없음';

  @override
  String get sortByDate => '날짜순 정렬';

  @override
  String get sortByStatus => '상태순 정렬';

  @override
  String get sortByName => '이름순 정렬';

  @override
  String get refresh => '새로고침';

  @override
  String get failedToLoadScanHistory => '스캔 기록 로딩 실패';

  @override
  String get noScanHistoryMessage => '완료된 스캔이 여기에 표시됩니다';

  @override
  String get about => '정보';

  @override
  String get parallelRequestsTooltip => '대상 모델에 대한 동시 요청 수';

  @override
  String get parallelAttemptsTooltip => '실패한 요청에 대한 재시도 횟수';

  @override
  String get generationsPerPrompt => '프롬프트당 생성';

  @override
  String get generationsPerPromptTooltip => '프로브당 생성할 테스트 프롬프트 수';

  @override
  String get evaluationThreshold => '평가 임계값';

  @override
  String get evaluationThresholdTooltip =>
      '테스트를 실패로 표시하기 위한 평가 임계값 (0.0 ~ 1.0)';

  @override
  String get modelHintOpenai => 'gpt-4, gpt-3.5-turbo 등';

  @override
  String get modelHintHuggingface => 'meta-llama/Llama-2-7b-chat-hf 등';

  @override
  String get modelHintReplicate => 'meta/llama-2-70b-chat 등';

  @override
  String get modelHintCohere => 'command, command-light 등';

  @override
  String get modelHintAnthropic => 'claude-3-opus-20240229 등';

  @override
  String get modelHintLitellm => 'gpt-4, claude-2 등';

  @override
  String get modelHintNim => 'meta/llama3-70b-instruct 등';

  @override
  String get modelHintOllama => 'llama2, mistral, codellama 등';

  @override
  String get probeResults => '프로브 결과';

  @override
  String get passed => '통과';

  @override
  String get failed => '실패';

  @override
  String get total => '총계';

  @override
  String get details => '세부 정보';

  @override
  String get summary => '요약';

  @override
  String get configuration => '구성';

  @override
  String get model => '모델';

  @override
  String get generator => '생성기';

  @override
  String get probesSelected => '선택된 프로브';

  @override
  String get startTime => '시작 시간';

  @override
  String get endTime => '종료 시간';

  @override
  String get duration => '소요 시간';

  @override
  String get connectionFailed => '연결 실패';

  @override
  String get checkBackendRunning => '백엔드 서버가 실행 중인지 확인하세요';

  @override
  String get language => '언어';

  @override
  String get selectLanguage => '언어 선택';

  @override
  String get english => '영어';

  @override
  String get korean => '한국어';

  @override
  String get japanese => '일본어';

  @override
  String get spanish => '스페인어';

  @override
  String get chinese => '중국어';

  @override
  String get apiConfiguration => 'API 설정';

  @override
  String get appearance => '외관';

  @override
  String get defaultScanSettings => '기본 스캔 설정';

  @override
  String get advancedSettings => '고급 설정';

  @override
  String get generations => '생성 수';

  @override
  String get generationsTooltip =>
      '프로브당 생성할 테스트 프롬프트 수. 값이 높을수록 더 철저한 테스트가 됩니다.';

  @override
  String get threshold => '임계값';

  @override
  String get thresholdTooltip => '테스트 실패 판정 평가 임계값. 값이 낮을수록 더 엄격한 탐지가 됩니다.';

  @override
  String get connectionTimeout => '연결 타임아웃';

  @override
  String get connectionTimeoutTooltip => '백엔드 연결 대기 시간.';

  @override
  String get receiveTimeout => '수신 타임아웃';

  @override
  String get receiveTimeoutTooltip =>
      '백엔드 응답 대기 시간. 느린 네트워크나 큰 LLM 응답의 경우 증가시키세요.';

  @override
  String get wsReconnectDelay => 'WS 재연결 지연';

  @override
  String get wsReconnectDelayTooltip => '연결 해제 후 WebSocket 재연결 시도 전 지연 시간.';

  @override
  String get targetEndpoint => '대상 엔드포인트';

  @override
  String get targetEndpointTooltip => '대상 LLM 서비스의 URL 엔드포인트.';

  @override
  String get restartForSettings => '네트워크 설정을 적용하려면 앱을 재시작하세요.';
}
