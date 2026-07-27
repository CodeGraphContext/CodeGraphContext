module ToughCases where

-- Tough Case 1: Type Classes and Instances
-- This defines a custom behavior that can be implemented by many types.
class Descriptive a where
    describe :: a -> String

data User = User { name :: String, age :: Int }
data Product = Product { title :: String, price :: Float }

instance Descriptive User where
    describe (User n a) = "User: " ++ n ++ " (" ++ show a ++ ")"

instance Descriptive Product where
    describe (Product t p) = "Product: " ++ t ++ " ($" ++ show p ++ ")"

-- Tough Case 2: Currying and Partial Application
-- Functions are first-class and can be partially applied.
add :: Int -> Int -> Int
add x y = x + y

addFive :: Int -> Int
addFive = add 5

-- Tough Case 3: Algebraic Data Types (ADTs) with Records
data Shape = Circle Float | Rectangle Float Float
    deriving (Show, Eq)

area :: Shape -> Float
area (Circle r) = pi * r * r
area (Rectangle w h) = w * h
