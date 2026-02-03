package com.example.geometry

abstract class Point(val x: Int, val y: Int) {
  def distanceTo(other: Point): Double
}

class Point2D(x: Int, y: Int) extends Point(x, y) {
  def distanceTo(other: Point): Double = {
    val dx = x - other.x
    val dy = y - other.y
    Math.sqrt(dx * dx + dy * dy)
  }
}

trait Resizable { 
  this: Point => // Self-type annotation
  
  def resize(factor: Double): Unit = {
    // resizing logic
  }
}
