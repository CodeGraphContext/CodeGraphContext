trait Greeter {
  def greet(name: String): String = s"Hello, $name"
}

trait Logging {
  def log(msg: String): Unit = println(s"[LOG] $msg")
}

case class User(name: String)

object User {
  def apply(name: String): User = new User(name.trim)
}

class AppService extends Greeter with Logging {
  def start(user: User): Unit = {
    log(greet(user.name))
  }
}
