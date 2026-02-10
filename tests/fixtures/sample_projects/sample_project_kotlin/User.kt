package com.example.project

interface Greeter {
    fun greet(): String
}

data class User(val name: String, val age: Int) : Greeter {
    override fun greet(): String {
        return "Hello, my name is $name and I am $age years old."
    }
}
