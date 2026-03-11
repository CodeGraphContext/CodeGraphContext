
/// Enums for testing
enum UserRole {
  admin,
  editor,
  viewer,
}

/// Mixin for auditable entities
mixin Auditable {
  late DateTime createdAt;
  late DateTime updatedAt;

  void markUpdated() {
    updatedAt = DateTime.now();
  }
}

/// Base class for all users
abstract class BaseUser {
  final String id;
  final String email;

  BaseUser(this.id, this.email);

  String getDisplayName();
}

/// A concrete User class implementing inheritance and mixins
class User extends BaseUser with Auditable {
  final String firstName;
  final String lastName;
  final UserRole role;

  User({
    required String id,
    required String email,
    required this.firstName,
    required this.lastName,
    this.role = UserRole.viewer,
  }) : super(id, email) {
    createdAt = DateTime.now();
    updatedAt = DateTime.now();
  }

  @override
  String getDisplayName() => '$firstName $lastName';

  bool isAdmin() => role == UserRole.admin;
}

/// Specialized AdminUser using inheritance
class AdminUser extends User {
  final List<String> permissions;

  AdminUser({
    required super.id,
    required super.email,
    required super.firstName,
    required super.lastName,
    this.permissions = const [],
  }) : super(role: UserRole.admin);

  void grantPermission(String permission) {
    if (!permissions.contains(permission)) {
      permissions.add(permission);
      markUpdated();
    }
  }
}
