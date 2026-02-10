package com.example

import com.example.shapes._
import com.example.utils.Calculator

object Main {
  def main(args: Array[String]): Unit = {
    println("Hello, Scala!")
    
    val calc = new Calculator()
    val sum = calc.add(5, 10)
    println(s"Sum: $sum")
    
    val circle = Circle(5.0)
    val area = circle.area
    println(s"Circle area: $area")
  }
}
