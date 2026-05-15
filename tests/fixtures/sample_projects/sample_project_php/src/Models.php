<?php

namespace App\Models;

class User {
    public function __construct(
        public int $id,
        public string $name,
        public ?string $email = null
    ) {}
}

interface Repository {
    public function findById(int $id): ?User;
}
