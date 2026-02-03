package com.example.utils

class Calculator {
  def add(a: Int, b: Int): Int = a + b
  
  def subtract(a: Int, b: Int): Int = a - b
  
  def multiply(a: Int, b: Int): Int = a * b
  
  def divide(a: Double, b: Double): Double = {
    if (b == 0) throw new IllegalArgumentException("Cannot divide by zero")
    a / b
  }
}

object StringUtils {
  def reverse(s: String): String = s.reverse
  
  def isPalindrome(s: String): Boolean = {
    val clean = s.toLowerCase.replaceAll("[^a-z0-9]", "")
    clean == clean.reverse
  }
}

// Generic class
class Box[T](val content: T) {
  def get: T = content
  def map[U](f: T => U): Box[U] = new Box(f(content))
}
