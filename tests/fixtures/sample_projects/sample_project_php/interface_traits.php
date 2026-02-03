<?php
interface Greeter {
    public function greet();
}

trait Logger {
    public function log($msg) {
        echo "[LOG] $msg\n";
    }
}

class Human implements Greeter {
    use Logger;
    public $name;
    
    public function __construct($name) {
        $this->name = $name;
    }
    
    public function greet() {
        return "Hello, I am {$this->name}";
    }
}

$shashank = new Human("Shashank");
echo $shashank->greet() . "\n";
$shashank->log("Greeting done");