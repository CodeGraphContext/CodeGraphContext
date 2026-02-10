package com.example.app.util;

import java.util.Collection;

public final class CollectionUtils {
    private CollectionUtils() {}

    public static <T extends Number> int sumOfSquares(Collection<T> nums) {
        return nums.stream().mapToInt(n -> {
            int v = n.intValue();
            return v * v;
        }).sum();
    }
}
