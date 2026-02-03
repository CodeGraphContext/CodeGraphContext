package com.example.complex

class Outer {
  private val secret = "I am outer"
  
  class Inner {
    def reveal: String = secret
  }
  
  object InnerObject {
    def check: Boolean = true
  }
}

object Outer {
  private val staticSecret = "I am static"
  
  def getStaticSecret: String = staticSecret
  
  class NestedInObject {
    def nothing: Unit = {}
  }
}
