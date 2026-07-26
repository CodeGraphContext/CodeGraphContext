<?php

require_once __DIR__ . '/src/Models.php';
require_once __DIR__ . '/src/Services.php';

use App\Models\User;
use App\Services\UserService;

$service = new UserService();
$user = new User(1, 'CGC Tester', 'tester@example.com');

$service->register($user);
$found = $service->findById(1);

if ($found) {
    echo "Found user: {$found->name}\n";
}
