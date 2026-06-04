package com.example.app

/**
 * Tough Case 1: Extension Functions
 * These are static methods but look like member methods.
 * Testing if the indexer can link 'shout' to its definition for a String.
 */
fun String.shout(): String {
    return this.uppercase() + "!!!"
}

fun testExtensions() {
    val message = "hello"
    println(message.shout())
}

/**
 * Tough Case 2: Companion Objects and Named Objects
 * Simulates static members and singletons.
 */
class DatabaseConnection private constructor() {
    companion object {
        private var instance: DatabaseConnection? = null
        
        fun getInstance(): DatabaseConnection {
            if (instance == null) {
                instance = DatabaseConnection()
            }
            return instance!!
        }
    }
    
    fun query(sql: String) {
        println("Executing: $sql")
    }
}

/**
 * Tough Case 3: Property Delegation
 * Tests the 'by' keyword which delegates getter/setter logic.
 */
class DelegateExample {
    val lazyValue: String by lazy {
        println("Computing lazy value...")
        "Computed"
    }
}

/**
 * Tough Case 4: Sealed Classes and Exhaustive When
 */
sealed class NetworkResult {
    data class Success(val data: String) : NetworkResult()
    data class Error(val message: String) : NetworkResult()
    object Loading : NetworkResult()
}

fun handleResult(result: NetworkResult) {
    when (result) {
        is NetworkResult.Success -> println("Got: ${result.data}")
        is NetworkResult.Error -> println("Error: ${result.message}")
        NetworkResult.Loading -> println("Loading...")
    }
}

/**
 * Tough Case 5: Higher Order Functions and Inlining
 */
inline fun <T> measureTime(block: () -> T): T {
    val start = System.currentTimeMillis()
    val result = block()
    val end = System.currentTimeMillis()
    println("Time: ${end - start}ms")
    return result
}
