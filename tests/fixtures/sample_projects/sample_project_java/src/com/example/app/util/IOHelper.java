package com.example.app.util;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;

public final class IOHelper {
    private IOHelper() {}

    public static String readFirstLine(String path) {
        try (BufferedReader br = new BufferedReader(new FileReader(path))) {
            String line = br.readLine();
            return line == null ? "" : line;
        } catch (IOException e) {
            throw new RuntimeException("unable to read: " + path, e);
        }
    }
}
