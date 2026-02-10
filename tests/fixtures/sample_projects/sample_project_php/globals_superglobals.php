<?php
// simulating for learning purposes
$_GET['name'] = "Shashank";
$_POST['age'] = 22;

// always validate user input
$name = htmlspecialchars($_GET['name']);
$age = filter_var($_POST['age'], FILTER_VALIDATE_INT);

echo $name . "\n";
echo $age . "\n";

$GLOBALS['x'] = 10;

function addFive(): void {
    $GLOBALS['x'] += 5;
}

addFive();
echo $GLOBALS['x'] . "\n";