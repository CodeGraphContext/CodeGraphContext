package com.example.project.advanced

// Abstract class hierarchy
abstract class Shape {
    abstract fun area(): Double
    open fun description(): String = "Unknown Shape"
}

class Circle(val radius: Double) : Shape() {
    override fun area(): Double = Math.PI * radius * radius
    override fun description(): String = "Circle with radius $radius"
}

// Sealed class hierarchy
sealed class Result {
    data class Success(val data: String) : Result()
    data class Error(val message: String) : Result()
    object Loading : Result()
}

// Nested and Inner classes
class Outer {
    private val bar: Int = 1
    
    class Nested {
        fun foo() = 2
    }
    
    inner class Inner {
        fun foo() = bar
    }
}

// Companion Object
class DatabaseConnection {
    companion object Factory {
        fun create(): DatabaseConnection = DatabaseConnection()
        const val TIMEOUT = 3000
    }
}

// Object declaration (Singleton)
object Configuration {
    var host: String = "localhost"
    var port: Int = 8080
}

interface Clickable {
    fun click()
    fun doubleClick() {
        click()
        click()
    }
}
