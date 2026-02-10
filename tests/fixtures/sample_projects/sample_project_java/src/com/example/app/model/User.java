package com.example.app.model;

public class User {
    private final String name;
    private final Role role;

    public User(String name, Role role) {
        this.name = name;
        this.role = role;
    }
    public String getName() { return name; }
    public Role getRole() { return role; }
}
