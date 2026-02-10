<?php
$dsn = "mysql:host=localhost;dbname=testdb";
$user = "root";
$pass = "";

try {
    $pdo = new PDO($dsn, $user, $pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    
    $pdo->exec("CREATE TABLE IF NOT EXISTS users(id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(50))");
    
    $stmt = $pdo->prepare("INSERT INTO users(name) VALUES(:name)");
    $stmt->execute(['name' => 'Shashank']);
    
    $result = $pdo->query("SELECT * FROM users");
    foreach($result as $row) {
        echo $row['name'] . "\n";
    }
} catch(PDOException $e) {
    echo "DB Error: " . $e->getMessage() . "\n";
}