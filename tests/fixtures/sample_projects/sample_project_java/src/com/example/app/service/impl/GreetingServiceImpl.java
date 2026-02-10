package com.example.app.service.impl;

import com.example.app.model.User;
import com.example.app.service.AbstractGreeter;
import com.example.app.service.GreetingService;

public class GreetingServiceImpl extends AbstractGreeter implements GreetingService {
    @Override
    public String greet(User user) {
        return base(user) + " (" + user.getRole() + ")";
    }
}
