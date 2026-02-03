package com.example.functional

object Functional {
  def applyFunc(x: Int, f: Int => Int): Int = f(x)
  
  def curriedAdd(x: Int)(y: Int): Int = x + y
  
  val multiplier: Int => Int = (x: Int) => x * 2
  
  def filterList(list: List[Int], p: Int => Boolean): List[Int] = {
    list.filter(p)
  }
}
