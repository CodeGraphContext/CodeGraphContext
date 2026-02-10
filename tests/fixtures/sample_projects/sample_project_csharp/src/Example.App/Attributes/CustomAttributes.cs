using System;

namespace Example.App.Attributes
{
    /// <summary>
    /// Custom attribute for marking deprecated methods
    /// </summary>
    [AttributeUsage(AttributeTargets.Method | AttributeTargets.Class, AllowMultiple = false)]
    public class DeprecatedAttribute : Attribute
    {
        public string Message { get; }
        public string AlternativeMethod { get; set; }
        
        public DeprecatedAttribute(string message)
        {
            Message = message;
        }
    }
    
    /// <summary>
    /// Custom attribute for logging
    /// </summary>
    [AttributeUsage(AttributeTargets.Method, AllowMultiple = true)]
    public class LogAttribute : Attribute
    {
        public string LogLevel { get; }
        
        public LogAttribute(string logLevel = "Info")
        {
            LogLevel = logLevel;
        }
    }
}
