using System;

namespace Example.App.Models
{
    /// <summary>
    /// Record type for immutable person data (C# 9.0+)
    /// </summary>
    public record Person(string FirstName, string LastName, int Age)
    {
        public string FullName => $"{FirstName} {LastName}";
        
        public bool IsAdult() => Age >= 18;
    }
    
    /// <summary>
    /// Record class with custom constructor
    /// </summary>
    public record Employee(string FirstName, string LastName, int Age, string Department) 
        : Person(FirstName, LastName, Age)
    {
        public string GetEmployeeInfo()
        {
            return $"{FullName} works in {Department}";
        }
    }
}
