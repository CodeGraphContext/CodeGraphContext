// Tough Case 1: Library Parts
// Splitting a single library across multiple files.
part 'tough_cases_part.dart';

/**
 * Tough Case 2: Mixins
 */
mixin Logger {
  void log(String message) {
    print('[LOG] $message');
  }
}

mixin Authenticator {
  bool isAuthenticated = false;
  void login() {
    isAuthenticated = true;
  }
}

class SecureService with Logger, Authenticator {
  void execute() {
    if (isAuthenticated) {
      log('Executing secure operation');
    }
  }
}

/**
 * Tough Case 3: Extensions
 */
extension StringSlug on String {
  String toSlug() {
    return this.toLowerCase().replaceAll(' ', '-');
  }
}

void testExtensions() {
  print('Hello World'.toSlug());
}

/**
 * Tough Case 4: Factory Constructors
 */
class Database {
  static final Database _instance = Database._internal();

  factory Database() {
    return _instance;
  }

  Database._internal();
  
  void connect() {
    print('Connected');
  }
}
