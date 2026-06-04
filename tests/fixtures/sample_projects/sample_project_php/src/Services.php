<?php

namespace App\Services;

use App\Models\User;
use App\Models\Repository;

class UserService implements Repository {
    /** @var User[] */
    private array $users = [];

    public function findById(int $id): ?User {
        return $this->users[$id] ?? null;
    }

    public function register(User $user): void {
        $this->users[$user->id] = $user;
    }
}

trait LoggerTrait {
    public function log(string $message): void {
        echo "[LOG] $message\n";
    }
}
