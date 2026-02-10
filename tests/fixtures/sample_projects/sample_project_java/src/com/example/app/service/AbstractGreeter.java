package com.example.app.service;

import com.example.app.annotations.Logged;
import com.example.app.model.User;

public abstract class AbstractGreeter {
    @Logged
    protected String base(User u) {
        return "Hello, " + u.getName();
    }
}
