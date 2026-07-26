abstract class Entity {
  String get id;
}

mixin Logger {
  void log(String message) {
    print('[LOG] $message');
  }
}

class User extends Entity with Logger {
  @override
  final String id;
  final String name;

  User(this.id, this.name);

  void performAction() {
    log('User $name performing action');
  }
}
