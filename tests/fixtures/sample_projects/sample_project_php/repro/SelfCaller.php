<?php
namespace App;
class SelfCaller {
    public function outer(): string { return $this->inner(); }
    public function inner(): string { return 'inner result'; }
}
