package com.example.app

/**
 * Tough Case 1: Implicits and Context Parameters (Scala 2/3)
 * Tracking where implicit values come from is extremely difficult.
 */
trait Database {
  fun execute(sql: String): Unit
}

object Database {
  // Implicit value defined in companion object
  implicit val defaultDb: Database = new Database {
    override fun execute(sql: String): Unit = println(s"Executing: $sql")
  }
}

class Repository {
  // Method taking an implicit parameter
  def save(data: String)(implicit db: Database): Unit = {
    db.execute(s"INSERT INTO table VALUES ('$data')")
  }

  def run(): Unit = {
    save("my_data") // Should resolve the implicit defaultDb from companion
  }
}

/**
 * Tough Case 2: Package Objects
 * Methods defined at the package level, not inside a class.
 */
// Normally defined in package.scala
object `package` {
  def globalHelper(): Unit = println("Package-level helper")
}

/**
 * Tough Case 3: Pattern Matching and Extractors
 */
case class User(name: String, age: Int)

object UserExtractor {
  def unapply(u: User): Option[(String, Int)] = Some((u.name, u.age))
}

class Matcher {
  def test(u: User): Unit = {
    u match {
      case UserExtractor(name, age) => println(s"Found $name aged $age")
      case _ => println("No match")
    }
  }
}

/**
 * Tough Case 4: Higher Kinded Types
 */
trait Container[F[_]] {
  def wrap[A](a: A): F[A]
}
