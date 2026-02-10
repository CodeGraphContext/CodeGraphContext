package com.example.project.annotations

annotation class Fancy(val id: Int)

@Fancy(1)
class Foo {
    @Fancy(2)
    fun baz(@Fancy(3) foo: Int): Int {
        return 1
    }
}

// Reflection usage
fun reflection() {
    val c = Foo::class
    for (a in c.annotations) {
        println(a)
    }
}
