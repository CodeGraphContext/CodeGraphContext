<?php
$file = "shashank.txt";

try {
    file_put_contents($file, "Hello Shashank\n");
    file_put_contents($file, "Welcome to PHP\n", FILE_APPEND);
    $data = file_get_contents($file);
    echo $data;
    unlink($file);
} catch (Exception $e) {
    echo "File error: " . $e->getMessage();
}