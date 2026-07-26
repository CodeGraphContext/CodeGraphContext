
import 'dart:math' as math;

/// Top-level function
double calculateDiscount(double price, double discountPercent) {
  if (discountPercent < 0 || discountPercent > 100) {
    throw ArgumentError('Invalid discount percentage');
  }
  return price * (1 - discountPercent / 100);
}

/// Helper function with optional and named parameters
String formatCurrency(double amount, {String symbol = '\$', int decimalPlaces = 2}) {
  return '$symbol${amount.toStringAsFixed(decimalPlaces)}';
}

/// Extension methods
extension StringValidator on String {
  bool isValidEmail() {
    final emailRegex = RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$');
    return emailRegex.hasMatch(this);
  }

  String capitalize() {
    if (isEmpty) return this;
    return '${this[0].toUpperCase()}${substring(1)}';
  }
}

/// Static utility class
class MathUtils {
  static const double pi = math.pi;

  static double areaOfCircle(double radius) {
    return pi * math.pow(radius, 2);
  }
  
  static double getHypotenuse(double a, double b) {
    return math.sqrt(math.pow(a, 2) + math.pow(b, 2));
  }
}
