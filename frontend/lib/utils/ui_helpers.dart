import 'package:flutter/material.dart';
import 'package:hydra/l10n/app_localizations.dart';

/// UI helper utilities for better error messages, animations, and transitions
class UIHelpers {
  /// Show a friendly error message
  static void showErrorSnackBar(
    BuildContext context,
    String message, {
    String? action,
    VoidCallback? onAction,
  }) {
    final l10n = AppLocalizations.of(context);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline, color: Colors.white),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                _getFriendlyErrorMessage(message, l10n),
                style: const TextStyle(fontSize: 14),
              ),
            ),
          ],
        ),
        backgroundColor: Colors.red.shade700,
        behavior: SnackBarBehavior.floating,
        action: action != null
            ? SnackBarAction(
                label: action,
                textColor: Colors.white,
                onPressed: onAction ?? () {},
              )
            : null,
        duration: const Duration(seconds: 4),
      ),
    );
  }

  /// Show a success message
  static void showSuccessSnackBar(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle_outline, color: Colors.white),
            const SizedBox(width: 12),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.green.shade700,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  /// Show an info message
  static void showInfoSnackBar(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.info_outline, color: Colors.white),
            const SizedBox(width: 12),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.blue.shade700,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  /// Convert technical error messages to user-friendly ones
  static String _getFriendlyErrorMessage(String error, AppLocalizations? l10n) {
    if (l10n == null) {
      // Fallback to English if l10n is not available
      return _getFriendlyErrorMessageFallback(error);
    }

    if (error.contains('Connection refused') || error.contains('Failed host lookup')) {
      return l10n.connectionError;
    }
    if (error.contains('SocketException')) {
      return l10n.networkError;
    }
    if (error.contains('TimeoutException')) {
      return l10n.timeoutError;
    }
    if (error.contains('401') || error.contains('Unauthorized')) {
      return l10n.authError;
    }
    if (error.contains('403') || error.contains('Forbidden')) {
      return l10n.forbiddenError;
    }
    if (error.contains('404') || error.contains('Not found')) {
      return l10n.notFoundError;
    }
    if (error.contains('500') || error.contains('Internal server error')) {
      return l10n.serverError;
    }
    if (error.contains('No scan history')) {
      return l10n.noScansFound;
    }

    // Return original message if no friendly match
    return error.length > 100 ? '${error.substring(0, 100)}...' : error;
  }

  /// Fallback error messages in English when l10n is not available
  static String _getFriendlyErrorMessageFallback(String error) {
    if (error.contains('Connection refused') || error.contains('Failed host lookup')) {
      return 'Cannot connect to server. Make sure the backend is running.';
    }
    if (error.contains('SocketException')) {
      return 'Network error. Please check your connection.';
    }
    if (error.contains('TimeoutException')) {
      return 'Request timed out. The server might be slow or unavailable.';
    }
    if (error.contains('401') || error.contains('Unauthorized')) {
      return 'Authentication failed. Please check your API key.';
    }
    if (error.contains('403') || error.contains('Forbidden')) {
      return 'Access denied. You may not have permission for this action.';
    }
    if (error.contains('404') || error.contains('Not found')) {
      return 'Resource not found. It may have been deleted.';
    }
    if (error.contains('500') || error.contains('Internal server error')) {
      return 'Server error. Please try again later.';
    }
    if (error.contains('No scan history')) {
      return 'No scans found. Complete a scan to see history.';
    }

    // Return original message if no friendly match
    return error.length > 100 ? '${error.substring(0, 100)}...' : error;
  }

  /// Custom page route with slide transition
  static Route<T> slideRoute<T>(Widget page, {AxisDirection direction = AxisDirection.left}) {
    return PageRouteBuilder<T>(
      pageBuilder: (context, animation, secondaryAnimation) => page,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        Offset begin;
        switch (direction) {
          case AxisDirection.up:
            begin = const Offset(0, 1);
            break;
          case AxisDirection.down:
            begin = const Offset(0, -1);
            break;
          case AxisDirection.left:
            begin = const Offset(1, 0);
            break;
          case AxisDirection.right:
            begin = const Offset(-1, 0);
            break;
        }

        const end = Offset.zero;
        const curve = Curves.easeInOut;

        var tween = Tween(begin: begin, end: end).chain(CurveTween(curve: curve));
        var offsetAnimation = animation.drive(tween);

        return SlideTransition(
          position: offsetAnimation,
          child: child,
        );
      },
      transitionDuration: const Duration(milliseconds: 300),
    );
  }

  /// Custom page route with fade transition
  static Route<T> fadeRoute<T>(Widget page) {
    return PageRouteBuilder<T>(
      pageBuilder: (context, animation, secondaryAnimation) => page,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        return FadeTransition(
          opacity: animation,
          child: child,
        );
      },
      transitionDuration: const Duration(milliseconds: 250),
    );
  }

  /// Custom page route with scale transition
  static Route<T> scaleRoute<T>(Widget page) {
    return PageRouteBuilder<T>(
      pageBuilder: (context, animation, secondaryAnimation) => page,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = 0.0;
        const end = 1.0;
        const curve = Curves.easeInOut;

        var tween = Tween(begin: begin, end: end).chain(CurveTween(curve: curve));
        var scaleAnimation = animation.drive(tween);

        return ScaleTransition(
          scale: scaleAnimation,
          child: child,
        );
      },
      transitionDuration: const Duration(milliseconds: 300),
    );
  }

  /// Show a loading dialog
  static void showLoadingDialog(BuildContext context, {String message = 'Loading...'}) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => PopScope(
        canPop: false,
        child: AlertDialog(
          content: Row(
            children: [
              const CircularProgressIndicator(),
              const SizedBox(width: 20),
              Expanded(child: Text(message)),
            ],
          ),
        ),
      ),
    );
  }

  /// Dismiss loading dialog
  static void dismissLoadingDialog(BuildContext context) {
    Navigator.of(context).pop();
  }

  /// Show a confirmation dialog
  static Future<bool> showConfirmationDialog(
    BuildContext context, {
    required String title,
    required String message,
    String confirmText = 'Confirm',
    String cancelText = 'Cancel',
    bool isDangerous = false,
  }) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(cancelText),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: isDangerous
                ? FilledButton.styleFrom(
                    backgroundColor: Colors.red,
                  )
                : null,
            child: Text(confirmText),
          ),
        ],
      ),
    );

    return result ?? false;
  }

  /// Create a tooltip widget
  static Widget buildTooltip({
    required String message,
    required Widget child,
    TooltipTriggerMode triggerMode = TooltipTriggerMode.tap,
  }) {
    return Tooltip(
      message: message,
      triggerMode: triggerMode,
      padding: const EdgeInsets.all(12),
      margin: const EdgeInsets.symmetric(horizontal: 20),
      decoration: BoxDecoration(
        color: Colors.grey.shade800,
        borderRadius: BorderRadius.circular(8),
      ),
      textStyle: const TextStyle(
        color: Colors.white,
        fontSize: 14,
      ),
      preferBelow: false,
      child: child,
    );
  }

  /// Animated container for cards
  static Widget animatedCard({
    required Widget child,
    Duration duration = const Duration(milliseconds: 300),
    Curve curve = Curves.easeInOut,
  }) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: duration,
      curve: curve,
      builder: (context, value, child) {
        return Opacity(
          opacity: value,
          child: Transform.translate(
            offset: Offset(0, 20 * (1 - value)),
            child: child,
          ),
        );
      },
      child: child,
    );
  }

  /// Strip ANSI escape codes from text
  /// Common ANSI codes like color, bold, etc. are removed
  static String stripAnsiCodes(String text) {
    // Remove ANSI escape sequences
    // Matches patterns like:
    // - \x1b[Xm (standard ANSI escape codes with ESC character)
    // - [Xm (short form without ESC, sometimes seen in output)
    // Where X can be one or more numbers separated by semicolons
    return text
        .replaceAll(RegExp(r'\x1b\[[0-9;]*m'), '')
        .replaceAll(RegExp(r'\[[0-9;]*m'), '');
  }
}

/// Extension on BuildContext for easier access to UI helpers
extension UIHelpersExtension on BuildContext {
  void showError(String message, {String? action, VoidCallback? onAction}) {
    UIHelpers.showErrorSnackBar(this, message, action: action, onAction: onAction);
  }

  void showSuccess(String message) {
    UIHelpers.showSuccessSnackBar(this, message);
  }

  void showInfo(String message) {
    UIHelpers.showInfoSnackBar(this, message);
  }

  void showLoading({String message = 'Loading...'}) {
    UIHelpers.showLoadingDialog(this, message: message);
  }

  void dismissLoading() {
    UIHelpers.dismissLoadingDialog(this);
  }

  Future<bool> confirm({
    required String title,
    required String message,
    String confirmText = 'Confirm',
    String cancelText = 'Cancel',
    bool isDangerous = false,
  }) {
    return UIHelpers.showConfirmationDialog(
      this,
      title: title,
      message: message,
      confirmText: confirmText,
      cancelText: cancelText,
      isDangerous: isDangerous,
    );
  }

  /// Show unsaved changes confirmation dialog
  /// Returns true if user wants to discard changes, false to stay
  Future<bool> confirmDiscardChanges() {
    return UIHelpers.showConfirmationDialog(
      this,
      title: 'Unsaved Changes',
      message: 'You have unsaved changes. Are you sure you want to leave? Your changes will be lost.',
      confirmText: 'Discard',
      cancelText: 'Stay',
      isDangerous: true,
    );
  }
}
