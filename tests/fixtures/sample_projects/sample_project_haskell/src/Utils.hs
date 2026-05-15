module Utils (formatGreeting) where

import Types

formatGreeting :: Greetable a => a -> String
formatGreeting x = "System Message: " ++ greet x
