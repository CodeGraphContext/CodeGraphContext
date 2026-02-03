package com.example.variables

class Config {
  val version: String = "1.0.0"
  var buildNumber: Int = 1
  
  private val secretKey: String = "xyz"
  protected val apiKey: String = "abc"
  
  lazy val expensiveCompute: Int = {
    Thread.sleep(100)
    42
  }
}
