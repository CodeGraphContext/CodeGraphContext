package com.example.app.misc;

public class Outer {
    private final String name;
    public Outer(String name) { this.name = name; }

    public class Inner {
        private final String name;
        public Inner(String name) { this.name = name; }
        public String combine() {
            Thread t = new Thread(() -> { /* no-op */ });
            t.start();
            return Outer.this.name + "+" + this.name;
        }
    }
}
