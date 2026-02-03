package com.example.shapes

sealed trait Shape {
  def area: Double
  def perimeter: Double
}

case class Circle(radius: Double) extends Shape {
  override def area: Double = Math.PI * radius * radius
  override def perimeter: Double = 2 * Math.PI * radius
}

case class Rectangle(width: Double, height: Double) extends Shape {
  override def area: Double = width * height
  override def perimeter: Double = 2 * (width + height)
}

object ShapeFactory {
  def createCircle(r: Double): Shape = Circle(r)
  def createRectangle(w: Double, h: Double): Shape = Rectangle(w, h)
}
