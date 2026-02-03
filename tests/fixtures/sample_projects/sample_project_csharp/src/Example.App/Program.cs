using System;
using System.Collections.Generic;
using Example.App.Models;
using Example.App.Services;
using Example.App.Utils;

namespace Example.App
{
    /// <summary>
    /// Main program entry point
    /// </summary>
    public class Program
    {
        public static void Main(string[] args)
        {
            // Create a greeting service
            IGreetingService greetingService = new GreetingService();
            
            // Create a user
            var user = new User("Alice", Role.Admin);
            
            // Greet the user
            string greeting = greetingService.Greet(user);
            Console.WriteLine(greeting);
            
            // Use collection utilities
            var numbers = new List<int> { 1, 2, 3, 4, 5 };
            int sumOfSquares = CollectionHelper.SumOfSquares(numbers);
            Console.WriteLine($"Sum of squares: {sumOfSquares}");
            
            // Use file helper
            try
            {
                string firstLine = FileHelper.ReadFirstLine("README.md");
                Console.WriteLine($"First line: {firstLine}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"File read failed: {ex.Message}");
            }
            
            // Demonstrate nested class
            var outer = new OuterClass("outer");
            var inner = outer.CreateInner("inner");
            Console.WriteLine(inner.Combine());
        }
    }
}
