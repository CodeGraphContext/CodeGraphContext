package models

sealed class Result {
    data class Success(val message: String) : Result()
    data class Error(val code: Int) : Result()
}

interface Processor {
    fun process(): Result
}
