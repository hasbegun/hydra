// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Japanese (`ja`).
class AppLocalizationsJa extends AppLocalizations {
  AppLocalizationsJa([String locale = 'ja']) : super(locale);

  @override
  String get appName => 'Hydra';

  @override
  String get appDescription => 'LLM脆弱性スキャナー';

  @override
  String get appVersion => '1.0.0';

  @override
  String get settings => '設定';

  @override
  String get selectModel => 'モデル選択';

  @override
  String get selectProbes => 'プローブ選択';

  @override
  String get advancedConfiguration => '詳細設定';

  @override
  String get browseProbes => 'プローブを閲覧';

  @override
  String get scanExecution => 'スキャン実行';

  @override
  String get scanResults => 'スキャン結果';

  @override
  String get detailedReport => '詳細レポート';

  @override
  String get scanHistory => 'スキャン履歴';

  @override
  String get myCustomProbes => 'カスタムプローブ';

  @override
  String get actions => 'アクション';

  @override
  String get scan => 'スキャン';

  @override
  String get startNewScan => '新しいスキャンを開始';

  @override
  String get browseProbesAction => 'プローブを閲覧';

  @override
  String get viewAllTests => 'すべてのテストを表示';

  @override
  String get writeProbe => 'プローブ作成';

  @override
  String get createCustomProbe => 'カスタムプローブを作成';

  @override
  String get myProbes => 'マイプローブ';

  @override
  String get manageSavedProbes => '保存したプローブを管理';

  @override
  String get history => '履歴';

  @override
  String get pastScans => '過去のスキャン';

  @override
  String get recentScans => '最近のスキャン';

  @override
  String get viewAll => 'すべて表示';

  @override
  String get llmVulnerabilityScanner => 'LLM脆弱性スキャナー';

  @override
  String get scanDescription =>
      'ジェイルブレイク、プロンプトインジェクション、毒性などの脆弱性について言語モデルをスキャンします。';

  @override
  String get poweredByGarak => 'Garak搭載';

  @override
  String get cancel => 'キャンセル';

  @override
  String get reset => 'リセット';

  @override
  String get testConnection => '接続テスト';

  @override
  String get resetToDefaults => 'デフォルトにリセット';

  @override
  String get saveSettings => '設定を保存';

  @override
  String get continueToProbeSelection => 'プローブ選択へ進む';

  @override
  String get clear => 'クリア';

  @override
  String get advanced => '詳細';

  @override
  String get quickStart => 'クイックスタート';

  @override
  String get goBack => '戻る';

  @override
  String get cancelScan => 'スキャンをキャンセル';

  @override
  String get viewResults => '結果を表示';

  @override
  String get retry => '再試行';

  @override
  String get backToHome => 'ホームに戻る';

  @override
  String get newProbe => '新規プローブ';

  @override
  String get validate => '検証';

  @override
  String get gotIt => '了解';

  @override
  String get delete => '削除';

  @override
  String get no => 'いいえ';

  @override
  String get yesCancelScan => 'はい、キャンセル';

  @override
  String get stay => '留まる';

  @override
  String get ok => 'OK';

  @override
  String get resetSettings => '設定をリセット';

  @override
  String get resetSettingsConfirm => 'すべての設定をデフォルト値にリセットしますか？';

  @override
  String get connectionTroubleshooting => '接続トラブルシューティング';

  @override
  String get apiKeyInformation => 'APIキー情報';

  @override
  String get apiKeyInfoContent =>
      'APIキーはオプションです。システムの環境変数としてAPIキーを既に設定している場合は、再度入力する必要はありません。このフィールドは環境変数を上書きする場合にのみ必要です。';

  @override
  String get aboutProbes => 'プローブについて';

  @override
  String get aboutProbesContent =>
      'プローブは言語モデルの特定の脆弱性をチェックするテストモジュールです。各プローブには、モデルが潜在的に有害な入力をどの程度適切に処理するかを評価するための複数のプロンプトが含まれています。';

  @override
  String get cancelScanConfirm => 'このスキャンをキャンセルしますか？';

  @override
  String get scanInProgress => 'スキャン進行中';

  @override
  String get scanInProgressContent => '現在スキャンが実行中です。キャンセルしますか？';

  @override
  String get exportSuccessful => 'エクスポート成功';

  @override
  String get detailedScanReport => '詳細スキャンレポート';

  @override
  String get deleteProbe => 'プローブを削除';

  @override
  String get deleteProbeConfirm => 'このプローブを削除しますか？この操作は取り消せません。';

  @override
  String get apiBaseUrl => 'APIベースURL';

  @override
  String get apiBaseUrlHint => 'http://localhost:8888/api/v1';

  @override
  String get apiBaseUrlDescription => 'スキャン操作用のバックエンドAPIエンドポイント';

  @override
  String get generatorType => 'ジェネレータータイプ';

  @override
  String get modelName => 'モデル名';

  @override
  String get modelNameDescription => '特定のモデル識別子を入力してください';

  @override
  String get apiKey => 'APIキー';

  @override
  String get apiKeyDescription => 'オプション：環境変数APIキーを上書き';

  @override
  String get apiKeyHint => 'sk-...';

  @override
  String get parallelRequests => '並列リクエスト';

  @override
  String get parallelRequestsHint => '例：5';

  @override
  String get parallelAttempts => '並列試行';

  @override
  String get parallelAttemptsHint => '例：3';

  @override
  String get randomSeed => 'ランダムシード';

  @override
  String get randomSeedHint => '例：42';

  @override
  String get searchProbes => 'プローブを検索...';

  @override
  String get probeName => 'プローブ名';

  @override
  String get probeNameHint => 'MyCustomProbe';

  @override
  String get descriptionOptional => '説明（オプション）';

  @override
  String get descriptionHint => 'このプローブがテストする内容の簡単な説明';

  @override
  String get probeCodeHint => '# ここにプローブコードを記述してください...';

  @override
  String get searchScans => 'スキャンを検索...';

  @override
  String get connectionError => 'サーバーに接続できません。バックエンドが実行中か確認してください。';

  @override
  String get networkError => 'ネットワークエラーです。接続を確認してください。';

  @override
  String get timeoutError => 'リクエストがタイムアウトしました。サーバーが遅いか利用できない可能性があります。';

  @override
  String get authError => '認証に失敗しました。APIキーを確認してください。';

  @override
  String get forbiddenError => 'アクセスが拒否されました。この操作の権限がない可能性があります。';

  @override
  String get notFoundError => 'リソースが見つかりません。削除された可能性があります。';

  @override
  String get serverError => 'サーバーエラーです。後でもう一度お試しください。';

  @override
  String get noScansFound => 'スキャンが見つかりません。スキャンを完了すると履歴が表示されます。';

  @override
  String get settingsSaved => '設定が正常に保存されました';

  @override
  String get settingsReset => '設定がデフォルトにリセットされました';

  @override
  String get connectionSuccessful => 'バックエンド接続成功！';

  @override
  String get testingConnection => '接続をテスト中...';

  @override
  String get selectGeneratorAndModel => 'ジェネレータータイプを選択し、モデル名を入力してください';

  @override
  String get selectAtLeastOneProbe => '少なくとも1つのプローブを選択するか、すべてを選択してください';

  @override
  String get enterProbeName => 'プローブ名を入力してください';

  @override
  String get enterProbeCode => 'プローブコードを入力してください';

  @override
  String get fixValidationErrors => '保存する前に検証エラーを修正してください';

  @override
  String get probeCreatedSuccess => 'プローブが正常に保存されました！';

  @override
  String get startingScan => 'スキャンを開始中...';

  @override
  String get darkMode => 'ダークモード';

  @override
  String get useDarkTheme => 'ダークテーマを使用';

  @override
  String get version => 'バージョン';

  @override
  String get description => '説明';

  @override
  String get garakLlmScanner => 'Garak LLMスキャナー';

  @override
  String get testingLlmsVulnerabilities => 'LLMの脆弱性テスト';

  @override
  String get openSource => 'オープンソース';

  @override
  String get apacheLicense => 'Apache 2.0ライセンス';

  @override
  String get connectionGuide => '接続ガイド';

  @override
  String get forAndroidEmulator => 'Androidエミュレーター：';

  @override
  String get useAndroidEmulatorUrl => 'http://10.0.2.2:8888/api/v1を使用';

  @override
  String get forIosSimulator => 'iOSシミュレーター：';

  @override
  String get useLocalhostUrl => 'http://localhost:8888/api/v1を使用';

  @override
  String get forDesktopWeb => 'デスクトップ/Web：';

  @override
  String get useDesktopUrl =>
      'http://localhost:8888/api/v1またはhttp://127.0.0.1:8888/api/v1を使用';

  @override
  String get selectAllProbes => 'すべてのプローブを選択';

  @override
  String get runComprehensiveScan => '包括的なスキャンを実行';

  @override
  String get allCategories => 'すべてのカテゴリ';

  @override
  String get inactive => '非アクティブ';

  @override
  String get active => 'アクティブ';

  @override
  String get fullName => '完全名';

  @override
  String get status => 'ステータス';

  @override
  String get tags => 'タグ';

  @override
  String get fastScan => '高速スキャン';

  @override
  String get fastScanDescription => '必須プローブによる高速スキャン';

  @override
  String get defaultScan => 'デフォルトスキャン';

  @override
  String get defaultScanDescription => '一般的な脆弱性をカバーするバランスの取れたスキャン';

  @override
  String get fullScan => 'フルスキャン';

  @override
  String get fullScanDescription => '最大限の徹底さを持つ包括的なスキャン';

  @override
  String get owaspLlmTop10 => 'OWASP LLM Top 10';

  @override
  String get owaspLlmTop10Description => 'OWASP LLM Top 10の脆弱性に焦点';

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
  String get ollamaSetup => 'Ollamaセットアップ';

  @override
  String get ollamaInstructions =>
      'Ollamaがローカルで実行中か確認してください。デフォルトではポート11434で実行されます。';

  @override
  String get popularModels => '人気モデル：llama2、llama3、gemma、mistral、codellama';

  @override
  String get quickPresets => 'クイックプリセット';

  @override
  String get startWithPreset => 'プリセット設定で開始（オプション）';

  @override
  String get configureTargetModel => 'ターゲットモデルを設定';

  @override
  String get selectLlmGenerator => 'テストするLLMジェネレーターとモデルを選択';

  @override
  String get passRate => '合格率';

  @override
  String get totalTests => '総テスト数';

  @override
  String get shareResults => '結果を共有';

  @override
  String get export => 'エクスポート';

  @override
  String get exportAsJson => 'JSONでエクスポート';

  @override
  String get exportAsHtml => 'HTMLでエクスポート';

  @override
  String get exportAsPdf => 'PDFでエクスポート';

  @override
  String get errorLoadingResults => '結果の読み込みエラー';

  @override
  String get failedToLoadProbes => 'プローブの読み込みに失敗';

  @override
  String get noScanHistory => 'スキャン履歴なし';

  @override
  String get sortByDate => '日付順';

  @override
  String get sortByStatus => 'ステータス順';

  @override
  String get sortByName => '名前順';

  @override
  String get refresh => '更新';

  @override
  String get failedToLoadScanHistory => 'スキャン履歴の読み込みに失敗';

  @override
  String get noScanHistoryMessage => '完了したスキャンがここに表示されます';

  @override
  String get about => '情報';

  @override
  String get parallelRequestsTooltip => 'ターゲットモデルへの同時リクエスト数';

  @override
  String get parallelAttemptsTooltip => '失敗したリクエストの再試行回数';

  @override
  String get generationsPerPrompt => 'プロンプトあたりの生成数';

  @override
  String get generationsPerPromptTooltip => 'プローブあたりに生成するテストプロンプト数';

  @override
  String get evaluationThreshold => '評価しきい値';

  @override
  String get evaluationThresholdTooltip => 'テストを失敗としてマークするための評価しきい値（0.0〜1.0）';

  @override
  String get modelHintOpenai => 'gpt-4、gpt-3.5-turboなど';

  @override
  String get modelHintHuggingface => 'meta-llama/Llama-2-7b-chat-hfなど';

  @override
  String get modelHintReplicate => 'meta/llama-2-70b-chatなど';

  @override
  String get modelHintCohere => 'command、command-lightなど';

  @override
  String get modelHintAnthropic => 'claude-3-opus-20240229など';

  @override
  String get modelHintLitellm => 'gpt-4、claude-2など';

  @override
  String get modelHintNim => 'meta/llama3-70b-instructなど';

  @override
  String get modelHintOllama => 'llama2、mistral、codellamaなど';

  @override
  String get probeResults => 'プローブ結果';

  @override
  String get passed => '合格';

  @override
  String get failed => '失敗';

  @override
  String get total => '合計';

  @override
  String get details => '詳細';

  @override
  String get summary => '概要';

  @override
  String get configuration => '設定';

  @override
  String get model => 'モデル';

  @override
  String get generator => 'ジェネレーター';

  @override
  String get probesSelected => '選択されたプローブ';

  @override
  String get startTime => '開始時間';

  @override
  String get endTime => '終了時間';

  @override
  String get duration => '所要時間';

  @override
  String get connectionFailed => '接続失敗';

  @override
  String get checkBackendRunning => 'バックエンドサーバーが実行中か確認してください';

  @override
  String get language => '言語';

  @override
  String get selectLanguage => '言語を選択';

  @override
  String get english => '英語';

  @override
  String get korean => '韓国語';

  @override
  String get japanese => '日本語';

  @override
  String get spanish => 'スペイン語';

  @override
  String get chinese => '中国語';

  @override
  String get apiConfiguration => 'API設定';

  @override
  String get appearance => '外観';

  @override
  String get defaultScanSettings => 'デフォルトスキャン設定';

  @override
  String get advancedSettings => '詳細設定';

  @override
  String get generations => '生成数';

  @override
  String get generationsTooltip => 'プローブごとに生成するテストプロンプトの数。値が高いほど徹底的なテストになります。';

  @override
  String get threshold => 'しきい値';

  @override
  String get thresholdTooltip => 'テスト失敗判定の評価しきい値。値が低いほど厳格な検出になります。';

  @override
  String get connectionTimeout => '接続タイムアウト';

  @override
  String get connectionTimeoutTooltip => 'バックエンド接続の待機時間。';

  @override
  String get receiveTimeout => '受信タイムアウト';

  @override
  String get receiveTimeoutTooltip =>
      'バックエンド応答の待機時間。遅いネットワークや大きなLLM応答の場合は増やしてください。';

  @override
  String get wsReconnectDelay => 'WS再接続遅延';

  @override
  String get wsReconnectDelayTooltip => '切断後のWebSocket再接続試行前の遅延時間。';

  @override
  String get targetEndpoint => 'ターゲットエンドポイント';

  @override
  String get targetEndpointTooltip => '対象LLMサービスのURLエンドポイント。';

  @override
  String get restartForSettings => 'ネットワーク設定を適用するにはアプリを再起動してください。';
}
