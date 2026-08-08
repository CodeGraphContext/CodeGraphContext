package com.example.app;

import java.util.List;
import java.util.function.Consumer;

/**
 * Tough Case 1: Nested and Inner Classes
 * Tests scope resolution across different levels of nesting.
 */
class Outer {
    private String outerSecret = "secret";

    void outerMethod() {
        System.out.println("Outer method called");
    }

    // Static nested class
    static class StaticNested {
        void nestedMethod() {
            // Cannot access outerSecret directly
            System.out.println("Static nested method");
        }
    }

    // Inner class (non-static)
    class Inner {
        void accessOuter() {
            outerMethod(); // Accessing outer member method
            System.out.println("Outer secret: " + outerSecret); // Accessing outer private field
        }
    }
}

/**
 * Tough Case 2: Anonymous Classes and Lambdas
 */
class CallbackTester {
    interface Processor {
        void process(String input);
    }

    public void testAnonymous() {
        // Classic anonymous class
        Processor p = new Processor() {
            @Override
            public void process(String input) {
                internalHelper(input);
            }
            
            private void internalHelper(String s) {
                System.out.println("Processing " + s);
            }
        };
        p.process("data");
    }

    public void testLambda() {
        // Lambda expression
        Consumer<String> c = (s) -> System.out.println("Lambda processing " + s);
        c.accept("more data");
    }
}

/**
 * Tough Case 3: Generics with Complex Bounds
 */
class GenericHandler<T extends Comparable<T>> {
    public void processList(List<? extends T> items) {
        for (T item : items) {
            item.compareTo(item);
        }
    }
}

/**
 * Tough Case 4: Overloaded Methods with Different Return Types (Simulated)
 */
/**
 * Tough Case 5: AOP and Dynamic Proxy Simulation
 * Simulates how frameworks like Spring or Dagger inject dependencies 
 * based on annotations, which creates "hidden" relationships.
 */
@interface Inject {}

class Repository {
    public void saveData(String data) {
        System.out.println("Saving: " + data);
    }
}

class Service {
    @Inject
    private Repository repository; // Relationship established via annotation

    public void doWork(String data) {
        // In a real AOP environment, 'repository' would be injected.
        // Indexer should ideally link this call to Repository.saveData
        if (repository != null) {
            repository.saveData(data);
        }
    }
}

/**
 * Tough Case 6: Enum with Methods and Fields
 */
enum Status {
    OPEN(1) {
        @Override
        public void transition() { System.out.println("Closing..."); }
    },
    CLOSED(0) {
        @Override
        public void transition() { System.out.println("Opening..."); }
    };

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/**
 * Tough Case 7: Dynamic Proxy and InvocationHandler
 * This is the ultimate "Blind Spot." The relationship between the 
 * interface call and the implementation is only resolved at runtime
 * through a proxy.
 */
interface DataService {
    void process(String input);
}

class DataServiceImpl implements DataService {
    @Override
    public void process(String input) {
        System.out.println("Processing in implementation: " + input);
    }
}

class SecurityProxyHandler implements InvocationHandler {
    private final Object target;

    public SecurityProxyHandler(Object target) {
        this.target = target;
    }

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        System.out.println("Security check before: " + method.getName());
        // Dynamic invocation of the target method
        return method.invoke(target, args);
    }
}

class ProxyFactory {
    public static DataService createSecureService() {
        DataService realService = new DataServiceImpl();
        return (DataService) Proxy.newProxyInstance(
            DataService.class.getClassLoader(),
            new Class[] { DataService.class },
            new SecurityProxyHandler(realService)
        );
    }
}

class Client {
    public void run() {
        DataService service = ProxyFactory.createSecureService();
        // Static analysis sees a call to DataService.process
        // A "Tough" indexer must find the link to DataServiceImpl.process
        service.process("Sensitive Data");
    }
}
