package com.example.project.android

// Hand-written stubs so this fixture compiles conceptually without the
// Android SDK, Hilt, Room or the Compose compiler on the test path.
annotation class Composable
annotation class Preview(val showBackground: Boolean = false, val name: String = "")
annotation class HiltViewModel
annotation class Entity(val tableName: String = "")
annotation class Dao
annotation class Query(val value: String)

@Composable
fun Greeting(name: String) {
    Label(name)
}

@Composable
fun Label(text: String) {
}

@Composable
@Preview(showBackground = true, name = "Greeting preview")
fun GreetingPreview() {
    Greeting("Android")
}

@HiltViewModel
class UserViewModel {
    fun load(): String {
        return "user"
    }
}

@Entity(tableName = "users")
class UserEntity(val id: Int, val name: String)

@Dao
interface UserDao {
    @Query("SELECT * FROM users")
    fun findAll(): List<UserEntity>
}

class PlainHelper {
    fun helped(): Int {
        return 1
    }
}
