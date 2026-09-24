package com.example.project.android.hilt

// Hand-written stubs so this fixture compiles conceptually without Hilt
// on the test path. Every object/class body below is written multi-line:
// a single-line object body (`object M { fun x() = 1 }`) is a pre-existing
// grammar misparse and would be silently dropped by the parser.
annotation class Module
annotation class Binds
annotation class Provides
annotation class Inject
annotation class HiltViewModel
annotation class Singleton

interface UserRepository {
    fun getUser(): String
}

class UserRepositoryImpl : UserRepository {
    override fun getUser(): String {
        return "user"
    }
}

interface NetworkClient {
    fun ping(): String
}

class NetworkClientImpl : NetworkClient {
    override fun ping(): String {
        return "pong"
    }
}

@Module
abstract class RepositoryModule {
    @Binds
    abstract fun bindUserRepository(impl: UserRepositoryImpl): UserRepository
}

@Module
object NetworkModule {
    @Provides
    fun provideNetworkClient(): NetworkClient {
        return NetworkClientImpl()
    }
}

@HiltViewModel
class UserViewModel @Inject constructor(
    private val userRepository: UserRepository
) {
    fun load(): String {
        return userRepository.getUser()
    }
}
