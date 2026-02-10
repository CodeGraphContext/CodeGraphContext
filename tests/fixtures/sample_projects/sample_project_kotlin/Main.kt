package com.example.project

import com.example.project.User

class Main {
    fun main(args: Array<String>) {
        val user = User("Shashank", 30)
        println(user.greet())
        
        val calculator = Calculator()
        println(calculator.add(5, 10))
    }
}

class Calculator {
    fun add(a: Int, b: Int): Int {
        return a + b
    }
}
