<?php
function greet($name, $age = 20) {
    return "Hello {$name}, you are {$age} years old";
}

function sumNumbers(...$nums) {
    return array_sum($nums);
}

$double = function($n) {
    return $n * 2;
};

echo greet("Shashank", 21) . "\n";
echo sumNumbers(1,2,3,4) . "\n";
echo $double(5) . "\n";
