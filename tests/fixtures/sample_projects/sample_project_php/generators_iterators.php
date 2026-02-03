<?php
function numbers(int $n): Generator {
    for($i = 0; $i < $n; $i++) {
        yield $i;
    }
}

foreach(numbers(5) as $num) {
    echo $num . "\n";
}

class MyIterator implements Iterator {
    private array $items = ["apple", "banana", "cherry"];
    private int $pos = 0;
    
    public function current(): mixed { 
        return $this->items[$this->pos]; 
    }
    public function key(): int { 
        return $this->pos; 
    }
    public function next(): void { 
        $this->pos++; 
    }
    public function rewind(): void { 
        $this->pos = 0; 
    }
    public function valid(): bool { 
        return isset($this->items[$this->pos]); 
    }
}

$it = new MyIterator();
foreach($it as $v) {
    echo $v . "\n";
}