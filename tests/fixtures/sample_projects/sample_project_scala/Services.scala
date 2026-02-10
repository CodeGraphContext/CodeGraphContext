package com.example.services

trait Service[T] {
  def process(item: T): Boolean
}

class StringService extends Service[String] {
  override def process(item: String): Boolean = item.nonEmpty
}

class IntService extends Service[Int] {
  override def process(item: Int): Boolean = item > 0
}

object ServiceManager {
  def runService[T](service: Service[T], item: T): Boolean = service.process(item)
}
