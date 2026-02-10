package com.example.project.properties

class User {
    var name: String = "John"
        get() = field.uppercase()
        set(value) {
            field = value.trim()
        }
        
    val isValid: Boolean
        get() = name.length > 0
        
    lateinit var data: String
    
    val lazyData: String by lazy {
        println("Computing...")
        "Heavy"
    }
}
