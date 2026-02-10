package com.example.project.edgecases

// 1. Destructuring Declarations
data class Point(val x: Int, val y: Int)
fun destructuring() {
    val (x, y) = Point(1, 2)
}

// 2. Type Aliases
typealias NodeSet = Set<String>
typealias FileTable<K> = MutableMap<K, MutableList<File>>

fun processNodes(nodes: NodeSet) {}

// 3. Anonymous Objects (Object Expressions)
fun createListener() {
    val listener = object : MouseAdapter() {
        override fun mouseClicked(e: MouseEvent) { 
            println("Clicked") 
        }
    }
}

// 4. Functional (SAM) Interfaces
fun interface IntPredicate {
    fun accept(i: Int): Boolean
}
val isEven = IntPredicate { it % 2 == 0 }

// 5. Generic Constraints
fun <T> copyWhenGreater(list: List<T>, threshold: T): List<String>
    where T : CharSequence,
          T : Comparable<T> {
    return list.filter { it > threshold }.map { it.toString() }
}

// 6. Contracts (Experimental)
import kotlin.contracts.*
fun require(condition: Boolean) {
    contract {
        returns() implies condition
    }
    if (!condition) throw IllegalArgumentException()
}

// 7. Value Classes (Inline Classes)
@JvmInline
value class Password(private val s: String)

// 8. Expect/Actual (Multiplatform) - purely syntax check if parser handles keywords
// expect fun format(str: String): String

// 9. Delegated Properties (Custom)
import kotlin.reflect.KProperty
class Delegate {
    operator fun getValue(thisRef: Any?, property: KProperty<*>): String {
        return "$thisRef, thank you for delegating '${property.name}' to me!"
    }
}
class Example {
    val p: String by Delegate()
}

// 10. Secondary Constructors
class Person {
    var children: MutableList<Person> = mutableListOf()
    constructor(parent: Person) {
        parent.children.add(this)
    }
}

// 11. Property in Constructor
class User(val name: String, var age: Int) 

// 12. Enum Classes with methods
enum class ProtocolState {
    WAITING {
        override fun signal() = TALKING
    },
    TALKING {
        override fun signal() = WAITING
    };
    abstract fun signal(): ProtocolState
}
