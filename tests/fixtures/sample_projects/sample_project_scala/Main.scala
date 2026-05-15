object Main {
  def main(args: Array[String]): Unit = {
    val service = new AppService()
    val user = User(" CGC User ")
    service.start(user)
  }
}
