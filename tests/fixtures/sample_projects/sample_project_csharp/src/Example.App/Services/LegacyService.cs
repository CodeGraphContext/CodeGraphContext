using System;
using Example.App.Attributes;

namespace Example.App.Services
{
    /// <summary>
    /// Service demonstrating use of custom attributes
    /// </summary>
    public class LegacyService
    {
        [Deprecated("This method is deprecated. Use NewMethod instead.", AlternativeMethod = "NewMethod")]
        public void OldMethod()
        {
            Console.WriteLine("This is the old method");
        }
        
        [Log("Info")]
        public void NewMethod()
        {
            Console.WriteLine("This is the new method");
        }
        
        [Log("Debug")]
        [Log("Trace")]
        public void MethodWithMultipleAttributes()
        {
            Console.WriteLine("Method with multiple log attributes");
        }
    }
}
