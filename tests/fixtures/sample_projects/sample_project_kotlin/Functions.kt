package com.example.project.functions

// Higher-Order Function
fun <T> List<T>.customFilter(predicate: (T) -> Boolean): List<T> {
    val result = ArrayList<T>()
    for (item in this) {
        if (predicate(item)) {
            result.add(item)
        }
    }
    return result
}

// Extension Function
fun String.removeSpaces(): String {
    return this.replace(" ", "")
}

// Inline Function
inline fun <T> lock(lock: Any, body: () -> T): T {
    // simulated lock
    return body()
}

// Function with default args
fun join(
    elements: List<String>, 
    separator: String = ", ", 
    prefix: String = "", 
    postfix: String = ""
): String {
    return prefix + elements.joinToString(separator) + postfix
}

// Single Expression Function
fun double(x: Int): Int = x * 2

class Calculator {
    // Operator overloading
    operator fun plus(other: Calculator): Calculator = Calculator()
    
    // Infix function
    infix fun add(x: Int): Int {
        return x + 10
    }
}

fun usage() {
    val list = listOf(1, 2, 3)
    val filtered = list.customFilter { it > 1 }
    
    val text = "Hello World"
    println(text.removeSpaces())
    
    val calc = Calculator()
    val res = calc add 5
    
    lock(calc) {
        println("Inside lock")
    }
}
