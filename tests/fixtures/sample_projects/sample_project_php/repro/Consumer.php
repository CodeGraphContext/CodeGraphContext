<?php
namespace App;
class Consumer {
    public function run(Service $service): string {
        return $service->doThing();
    }
}
