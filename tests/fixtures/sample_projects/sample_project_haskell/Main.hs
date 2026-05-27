module Main where

import Types
import Utils

main :: IO ()
main = do
    let p = Person "CGC User" 30
    putStrLn $ formatGreeting p
