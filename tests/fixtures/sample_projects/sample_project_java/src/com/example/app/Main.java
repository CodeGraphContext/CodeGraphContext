package com.example.app;

import com.example.app.model.Role;
import com.example.app.model.User;
import com.example.app.service.GreetingService;
import com.example.app.service.impl.GreetingServiceImpl;
import com.example.app.util.CollectionUtils;
import com.example.app.util.IOHelper;

import java.util.List;

public class Main {
    public static void main(String[] args) {
        GreetingService svc = new GreetingServiceImpl();
        User u = new User("Priya", Role.ADMIN);
        System.out.println(svc.greet(u));

        int sumSquares = CollectionUtils.sumOfSquares(List.of(1, 2, 3, 4, 5));
        System.out.println("sumSquares=" + sumSquares);

        try {
            String first = IOHelper.readFirstLine("README.md");
            System.out.println("firstLine=" + first);
        } catch (RuntimeException e) {
            System.out.println("IO failed: " + e.getMessage());
        }

        com.example.app.misc.Outer outer = new com.example.app.misc.Outer("outer");
        com.example.app.misc.Outer.Inner inner = outer.new Inner("inner");
        System.out.println(inner.combine());
    }
}
