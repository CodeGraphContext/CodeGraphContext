// This is a script file
println("Starting script...")

val x = 10
val y = 20

def sum(a: Int, b: Int): Int = a + b

println(s"Result: ${sum(x, y)}")

class ScriptHelper {
  def help: String = "Helping"
}

val helper = new ScriptHelper()
println(helper.help)
