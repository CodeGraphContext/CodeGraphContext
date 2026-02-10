package com.example.animals

trait Animal {
  val name: String
  def speak(): String
}

trait Mammal extends Animal {
  def hasFur: Boolean = true
}

trait CanRun {
  def run(speed: Double): String = s"Running at $speed km/h"
}

class Dog(override val name: String) extends Mammal with CanRun {
  override def speak(): String = "Woof!"
}

class Cat(override val name: String) extends Mammal {
  override def speak(): String = "Meow"
  override val hasFur: Boolean = true
}
