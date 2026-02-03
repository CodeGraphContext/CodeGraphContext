using System;
using System.Collections.Generic;
using System.Linq;

namespace Example.App.Utils
{
    /// <summary>
    /// Helper class for collection operations
    /// </summary>
    public static class CollectionHelper
    {
        /// <summary>
        /// Calculates the sum of squares of all numbers in the collection
        /// </summary>
        public static int SumOfSquares(IEnumerable<int> numbers)
        {
            if (numbers == null)
            {
                throw new ArgumentNullException(nameof(numbers));
            }
            
            return numbers.Select(n => n * n).Sum();
        }
        
        /// <summary>
        /// Filters even numbers from the collection
        /// </summary>
        public static IEnumerable<int> FilterEven(IEnumerable<int> numbers)
        {
            return numbers.Where(n => n % 2 == 0);
        }
        
        /// <summary>
        /// Finds the maximum value in the collection
        /// </summary>
        public static int FindMax(IEnumerable<int> numbers)
        {
            if (!numbers.Any())
            {
                throw new InvalidOperationException("Collection is empty");
            }
            
            return numbers.Max();
        }
    }
}
