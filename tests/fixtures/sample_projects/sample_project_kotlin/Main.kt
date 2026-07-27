import models.*

class DataProcessor(val data: String) : Processor {
    override fun process(): Result {
        return if (data.isNotEmpty()) {
            Result.Success("Processed: $data")
        } else {
            Result.Error(404)
        }
    }
}

fun String.shout() = this.uppercase() + "!!!"

fun main() {
    val processor = DataProcessor("Hello CGC")
    val result = processor.process()
    
    when (result) {
        is Result.Success -> println(result.message.shout())
        is Result.Error -> println("Error code: ${result.code}")
    }
}
