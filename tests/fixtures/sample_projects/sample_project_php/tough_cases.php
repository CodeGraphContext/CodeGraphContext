<?php

namespace App\Tough;

/**
 * Tough Case 1: Trait Conflict Resolution and Aliasing
 * This tests if the indexer can correctly identify which trait method is being called.
 */
trait Alpha {
    public function execute() { return "Alpha"; }
    public function shared() { return "AlphaShared"; }
}

trait Beta {
    public function execute() { return "Beta"; }
    public function shared() { return "BetaShared"; }
}

class ConflictResolver {
    use Alpha, Beta {
        Beta::execute insteadof Alpha;
        Alpha::shared insteadof Beta;
        Beta::shared as betaSharedAlias;
    }

    public function run() {
        $this->execute(); // Should link to Beta::execute
        $this->shared();  // Should link to Alpha::shared
        $this->betaSharedAlias(); // Should link to Beta::shared
    }
}

/**
 * Tough Case 2: Anonymous Classes and Interface Implementation
 * This tests tracking relationships for objects that don't have a named class.
 */
interface Task {
    public function perform(): string;
}

class TaskFactory {
    public function createDynamicTask($name): Task {
        return new class($name) implements Task {
            private $name;
            public function __construct($name) { $this->name = $name; }
            public function perform(): string {
                return "Performing task: " . $this->name;
            }
        };
    }
}

/**
 * Tough Case 3: Dynamic Method Calls and Reflection
 * Tests the indexer's ability to handle (or gracefully fail/log) dynamic calls.
 */
class DynamicInvoker {
    public function targetMethod($arg) {
        return "Target reached with $arg";
    }

    public function invokeDynamically($methodName) {
        // Variable method name
        $this->$methodName("hello"); 
        
        // call_user_func
        call_user_func([$this, 'targetMethod'], "world");
    }
}

/**
 * Tough Case 4: Deeply Nested Closures and Scope
 */
class ClosureTest {
    public function outer($x) {
        $multiplier = 2;
        return function($y) use ($x, $multiplier) {
            return function($z) use ($x, $y, $multiplier) {
                return ($x + $y + $z) * $multiplier;
            };
        };
    }
}

/**
 * Tough Case 5: PHP 8 Attributes (Metaprogramming)
 */
#[Attribute]
class Injectable {
    public function __construct(public string $serviceName) {}
}

#[Injectable(serviceName: "database")]
class InstrumentedService {
    public function doWork() {
        return "Work done";
    }
}
