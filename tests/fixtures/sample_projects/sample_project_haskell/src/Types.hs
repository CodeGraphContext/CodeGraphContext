module Types where

data Person = Person { name :: String, age :: Int } deriving (Show)

class Greetable a where
    greet :: a -> String

instance Greetable Person where
    greet (Person n _) = "Hello, " ++ n
