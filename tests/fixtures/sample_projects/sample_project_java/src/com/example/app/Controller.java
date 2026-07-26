package com.example.app;

import com.example.app.service.WorkService;

/**
 * Demonstrates setter-based DI field injection (Spring XML-style).
 * The 'workService' field is injected via setWorkService(). CGC must
 * resolve workService.doWork() as a cross-file CALLS edge to WorkService.
 */
public class Controller {
    private WorkService workService;

    public void setWorkService(WorkService workService) {
        this.workService = workService;
    }

    public String handle(String input) {
        String result = workService.doWork(input);
        int computed = workService.computeResult(42);
        return result + " (" + computed + ")";
    }
}
