// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get appName => 'Hydra';

  @override
  String get appDescription => 'LLM漏洞扫描器';

  @override
  String get appVersion => '1.0.0';

  @override
  String get settings => '设置';

  @override
  String get selectModel => '选择模型';

  @override
  String get selectProbes => '选择探针';

  @override
  String get advancedConfiguration => '高级配置';

  @override
  String get browseProbes => '浏览探针';

  @override
  String get scanExecution => '扫描执行';

  @override
  String get scanResults => '扫描结果';

  @override
  String get detailedReport => '详细报告';

  @override
  String get scanHistory => '扫描历史';

  @override
  String get myCustomProbes => '我的自定义探针';

  @override
  String get actions => '操作';

  @override
  String get scan => '扫描';

  @override
  String get startNewScan => '开始新扫描';

  @override
  String get browseProbesAction => '浏览探针';

  @override
  String get viewAllTests => '查看所有测试';

  @override
  String get writeProbe => '编写探针';

  @override
  String get createCustomProbe => '创建自定义探针';

  @override
  String get myProbes => '我的探针';

  @override
  String get manageSavedProbes => '管理已保存的探针';

  @override
  String get history => '历史';

  @override
  String get pastScans => '过去的扫描';

  @override
  String get recentScans => '最近扫描';

  @override
  String get viewAll => '查看全部';

  @override
  String get llmVulnerabilityScanner => 'LLM漏洞扫描器';

  @override
  String get scanDescription => '扫描您的语言模型以查找漏洞，包括越狱、提示注入、毒性等。';

  @override
  String get poweredByGarak => '由Garak驱动';

  @override
  String get cancel => '取消';

  @override
  String get reset => '重置';

  @override
  String get testConnection => '测试连接';

  @override
  String get resetToDefaults => '重置为默认值';

  @override
  String get saveSettings => '保存设置';

  @override
  String get continueToProbeSelection => '继续选择探针';

  @override
  String get clear => '清除';

  @override
  String get advanced => '高级';

  @override
  String get quickStart => '快速开始';

  @override
  String get goBack => '返回';

  @override
  String get cancelScan => '取消扫描';

  @override
  String get viewResults => '查看结果';

  @override
  String get retry => '重试';

  @override
  String get backToHome => '返回主页';

  @override
  String get newProbe => '新建探针';

  @override
  String get validate => '验证';

  @override
  String get gotIt => '知道了';

  @override
  String get delete => '删除';

  @override
  String get no => '否';

  @override
  String get yesCancelScan => '是的，取消';

  @override
  String get stay => '留下';

  @override
  String get ok => '确定';

  @override
  String get resetSettings => '重置设置';

  @override
  String get resetSettingsConfirm => '将所有设置重置为默认值？';

  @override
  String get connectionTroubleshooting => '连接故障排除';

  @override
  String get apiKeyInformation => 'API密钥信息';

  @override
  String get apiKeyInfoContent =>
      'API密钥在此处是可选的。如果您已在系统上将API密钥设置为环境变量，则无需再次输入。此字段仅在您想要覆盖环境变量时才需要。';

  @override
  String get aboutProbes => '关于探针';

  @override
  String get aboutProbesContent =>
      '探针是检查语言模型特定漏洞的测试模块。每个探针包含多个提示，旨在评估模型处理潜在有害输入的能力。';

  @override
  String get cancelScanConfirm => '您确定要取消此扫描吗？';

  @override
  String get scanInProgress => '扫描进行中';

  @override
  String get scanInProgressContent => '当前有扫描正在运行。您想取消它吗？';

  @override
  String get exportSuccessful => '导出成功';

  @override
  String get detailedScanReport => '详细扫描报告';

  @override
  String get deleteProbe => '删除探针';

  @override
  String get deleteProbeConfirm => '您确定要删除此探针吗？此操作无法撤消。';

  @override
  String get apiBaseUrl => 'API基础URL';

  @override
  String get apiBaseUrlHint => 'http://localhost:8888/api/v1';

  @override
  String get apiBaseUrlDescription => '扫描操作的后端API端点';

  @override
  String get generatorType => '生成器类型';

  @override
  String get modelName => '模型名称';

  @override
  String get modelNameDescription => '输入具体的模型标识符';

  @override
  String get apiKey => 'API密钥';

  @override
  String get apiKeyDescription => '可选：覆盖环境变量API密钥';

  @override
  String get apiKeyHint => 'sk-...';

  @override
  String get parallelRequests => '并行请求';

  @override
  String get parallelRequestsHint => '例如：5';

  @override
  String get parallelAttempts => '并行尝试';

  @override
  String get parallelAttemptsHint => '例如：3';

  @override
  String get randomSeed => '随机种子';

  @override
  String get randomSeedHint => '例如：42';

  @override
  String get searchProbes => '搜索探针...';

  @override
  String get probeName => '探针名称';

  @override
  String get probeNameHint => 'MyCustomProbe';

  @override
  String get descriptionOptional => '描述（可选）';

  @override
  String get descriptionHint => '此探针测试内容的简要描述';

  @override
  String get probeCodeHint => '# 在此处编写您的探针代码...';

  @override
  String get searchScans => '搜索扫描...';

  @override
  String get connectionError => '无法连接到服务器。请确保后端正在运行。';

  @override
  String get networkError => '网络错误。请检查您的连接。';

  @override
  String get timeoutError => '请求超时。服务器可能很慢或不可用。';

  @override
  String get authError => '身份验证失败。请检查您的API密钥。';

  @override
  String get forbiddenError => '访问被拒绝。您可能没有此操作的权限。';

  @override
  String get notFoundError => '未找到资源。它可能已被删除。';

  @override
  String get serverError => '服务器错误。请稍后重试。';

  @override
  String get noScansFound => '未找到扫描。完成扫描以查看历史记录。';

  @override
  String get settingsSaved => '设置保存成功';

  @override
  String get settingsReset => '设置已重置为默认值';

  @override
  String get connectionSuccessful => '后端连接成功！';

  @override
  String get testingConnection => '正在测试连接...';

  @override
  String get selectGeneratorAndModel => '请选择生成器类型并输入模型名称';

  @override
  String get selectAtLeastOneProbe => '请至少选择一个探针或全选';

  @override
  String get enterProbeName => '请输入探针名称';

  @override
  String get enterProbeCode => '请输入探针代码';

  @override
  String get fixValidationErrors => '请在保存前修复验证错误';

  @override
  String get probeCreatedSuccess => '探针保存成功！';

  @override
  String get startingScan => '正在启动扫描...';

  @override
  String get darkMode => '深色模式';

  @override
  String get useDarkTheme => '使用深色主题';

  @override
  String get version => '版本';

  @override
  String get description => '描述';

  @override
  String get garakLlmScanner => 'Garak LLM扫描器';

  @override
  String get testingLlmsVulnerabilities => '测试LLM漏洞';

  @override
  String get openSource => '开源';

  @override
  String get apacheLicense => 'Apache 2.0许可证';

  @override
  String get connectionGuide => '连接指南';

  @override
  String get forAndroidEmulator => 'Android模拟器：';

  @override
  String get useAndroidEmulatorUrl => '使用 http://10.0.2.2:8888/api/v1';

  @override
  String get forIosSimulator => 'iOS模拟器：';

  @override
  String get useLocalhostUrl => '使用 http://localhost:8888/api/v1';

  @override
  String get forDesktopWeb => '桌面/Web：';

  @override
  String get useDesktopUrl =>
      '使用 http://localhost:8888/api/v1 或 http://127.0.0.1:8888/api/v1';

  @override
  String get selectAllProbes => '选择所有探针';

  @override
  String get runComprehensiveScan => '运行全面扫描';

  @override
  String get allCategories => '所有类别';

  @override
  String get inactive => '未激活';

  @override
  String get active => '已激活';

  @override
  String get fullName => '全名';

  @override
  String get status => '状态';

  @override
  String get tags => '标签';

  @override
  String get fastScan => '快速扫描';

  @override
  String get fastScanDescription => '使用基本探针进行快速扫描';

  @override
  String get defaultScan => '默认扫描';

  @override
  String get defaultScanDescription => '覆盖常见漏洞的平衡扫描';

  @override
  String get fullScan => '完整扫描';

  @override
  String get fullScanDescription => '最大彻底性的全面扫描';

  @override
  String get owaspLlmTop10 => 'OWASP LLM Top 10';

  @override
  String get owaspLlmTop10Description => '专注于OWASP LLM Top 10漏洞';

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
  String get ollamaSetup => 'Ollama设置';

  @override
  String get ollamaInstructions => '确保Ollama在本地运行。默认情况下，它在端口11434上运行。';

  @override
  String get popularModels => '热门模型：llama2、llama3、gemma、mistral、codellama';

  @override
  String get quickPresets => '快速预设';

  @override
  String get startWithPreset => '从预设配置开始（可选）';

  @override
  String get configureTargetModel => '配置目标模型';

  @override
  String get selectLlmGenerator => '选择要测试的LLM生成器和模型';

  @override
  String get passRate => '通过率';

  @override
  String get totalTests => '总测试数';

  @override
  String get shareResults => '分享结果';

  @override
  String get export => '导出';

  @override
  String get exportAsJson => '导出为JSON';

  @override
  String get exportAsHtml => '导出为HTML';

  @override
  String get exportAsPdf => '导出为PDF';

  @override
  String get errorLoadingResults => '加载结果时出错';

  @override
  String get failedToLoadProbes => '加载探针失败';

  @override
  String get noScanHistory => '无扫描历史';

  @override
  String get sortByDate => '按日期排序';

  @override
  String get sortByStatus => '按状态排序';

  @override
  String get sortByName => '按名称排序';

  @override
  String get refresh => '刷新';

  @override
  String get failedToLoadScanHistory => '加载扫描历史失败';

  @override
  String get noScanHistoryMessage => '您完成的扫描将显示在此处';

  @override
  String get about => '关于';

  @override
  String get parallelRequestsTooltip => '对目标模型的并发请求数';

  @override
  String get parallelAttemptsTooltip => '失败请求的重试次数';

  @override
  String get generationsPerPrompt => '每个提示的生成数';

  @override
  String get generationsPerPromptTooltip => '每个探针要生成的测试提示数';

  @override
  String get evaluationThreshold => '评估阈值';

  @override
  String get evaluationThresholdTooltip => '将测试标记为失败的评估阈值（0.0到1.0）';

  @override
  String get modelHintOpenai => 'gpt-4、gpt-3.5-turbo等';

  @override
  String get modelHintHuggingface => 'meta-llama/Llama-2-7b-chat-hf等';

  @override
  String get modelHintReplicate => 'meta/llama-2-70b-chat等';

  @override
  String get modelHintCohere => 'command、command-light等';

  @override
  String get modelHintAnthropic => 'claude-3-opus-20240229等';

  @override
  String get modelHintLitellm => 'gpt-4、claude-2等';

  @override
  String get modelHintNim => 'meta/llama3-70b-instruct等';

  @override
  String get modelHintOllama => 'llama2、mistral、codellama等';

  @override
  String get probeResults => '探针结果';

  @override
  String get passed => '通过';

  @override
  String get failed => '失败';

  @override
  String get total => '总计';

  @override
  String get details => '详情';

  @override
  String get summary => '摘要';

  @override
  String get configuration => '配置';

  @override
  String get model => '模型';

  @override
  String get generator => '生成器';

  @override
  String get probesSelected => '已选探针';

  @override
  String get startTime => '开始时间';

  @override
  String get endTime => '结束时间';

  @override
  String get duration => '持续时间';

  @override
  String get connectionFailed => '连接失败';

  @override
  String get checkBackendRunning => '请检查后端服务器是否正在运行';

  @override
  String get language => '语言';

  @override
  String get selectLanguage => '选择语言';

  @override
  String get english => '英语';

  @override
  String get korean => '韩语';

  @override
  String get japanese => '日语';

  @override
  String get spanish => '西班牙语';

  @override
  String get chinese => '中文';

  @override
  String get apiConfiguration => 'API配置';

  @override
  String get appearance => '外观';

  @override
  String get defaultScanSettings => '默认扫描设置';

  @override
  String get advancedSettings => '高级设置';

  @override
  String get generations => '生成数';

  @override
  String get generationsTooltip => '每个探针生成的测试提示数。数值越高，测试越彻底。';

  @override
  String get threshold => '阈值';

  @override
  String get thresholdTooltip => '标记测试失败的评估阈值。数值越低，检测越严格。';

  @override
  String get connectionTimeout => '连接超时';

  @override
  String get connectionTimeoutTooltip => '等待与后端建立连接的时间。';

  @override
  String get receiveTimeout => '接收超时';

  @override
  String get receiveTimeoutTooltip => '等待后端响应的时间。对于慢速网络或大型LLM响应，请增加此值。';

  @override
  String get wsReconnectDelay => 'WS重连延迟';

  @override
  String get wsReconnectDelayTooltip => '断开连接后尝试重新连接WebSocket前的延迟时间。';

  @override
  String get targetEndpoint => '目标端点';

  @override
  String get targetEndpointTooltip => '目标LLM服务的URL端点。';

  @override
  String get restartForSettings => '重启应用以使网络设置生效。';
}
