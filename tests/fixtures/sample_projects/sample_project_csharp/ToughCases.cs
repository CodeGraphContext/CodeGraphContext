using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace ToughCases
{
    /**
     * Tough Case 1: Partial Classes and Methods
     * The definition of a single class is split across multiple files.
     * Indexers must merge these into a single node.
     */
    public partial class MultiPartClass
    {
        public void MethodFromPartA() {
            MethodFromPartB(); // Calling method defined in another file
        }
        
        partial void PartialDefinition(); // Defined here, implemented elsewhere
    }

    /**
     * Tough Case 2: Extension Methods
     * Similar to Kotlin, these look like instance methods but are static.
     */
    public static class StringExtensions
    {
        public static string ToSlug(this string str)
        {
            return str.ToLower().Replace(" ", "-");
        }
    }

    /**
     * Tough Case 3: LINQ and Lambda Expressions
     * Tests if the indexer can track calls inside query expressions.
     */
    public class DataProcessor
    {
        public void Process(List<string> items)
        {
            var results = items
                .Where(i => i.Length > 5)
                .Select(i => i.ToSlug()); // Extension method call inside LINQ
        }
    }

    /**
     * Tough Case 4: Async/Await State Machines
     */
    public class AsyncService
    {
        public async Task<string> FetchDataAsync()
        {
            await Task.Delay(100);
            return "Data";
        }

        public async Task RunAsync()
        {
            var data = await FetchDataAsync();
            Console.WriteLine(data);
        }
    }

    /**
     * Tough Case 5: Attributes and Reflection
     */
    [AttributeUsage(AttributeTargets.Class)]
    public class InjectableAttribute : Attribute { }

    [Injectable]
    public class Service { }
}
