package com.example.project.coroutines

import kotlinx.coroutines.*

suspend fun doWorld() {
    delay(1000L)
    println("World!")
}

fun main() = runBlocking {
    launch {
        doWorld()
    }
    println("Hello")
}

class AsyncProcessor {
    suspend fun process(): String = coroutineScope {
        val deferred = async { 
            delay(500)
            "Result"
        }
        deferred.await()
    }
}
