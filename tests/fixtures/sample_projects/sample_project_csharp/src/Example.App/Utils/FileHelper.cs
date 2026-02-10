using System;
using System.IO;

namespace Example.App.Utils
{
    /// <summary>
    /// Helper class for file I/O operations
    /// </summary>
    public static class FileHelper
    {
        /// <summary>
        /// Reads the first line from a file
        /// </summary>
        public static string ReadFirstLine(string filePath)
        {
            if (string.IsNullOrEmpty(filePath))
            {
                throw new ArgumentException("File path cannot be null or empty", nameof(filePath));
            }
            
            if (!File.Exists(filePath))
            {
                throw new FileNotFoundException($"File not found: {filePath}");
            }
            
            using (var reader = new StreamReader(filePath))
            {
                return reader.ReadLine() ?? string.Empty;
            }
        }
        
        /// <summary>
        /// Writes text to a file
        /// </summary>
        public static void WriteToFile(string filePath, string content)
        {
            if (string.IsNullOrEmpty(filePath))
            {
                throw new ArgumentException("File path cannot be null or empty", nameof(filePath));
            }
            
            File.WriteAllText(filePath, content);
        }
        
        /// <summary>
        /// Checks if a file exists
        /// </summary>
        public static bool FileExists(string filePath)
        {
            return !string.IsNullOrEmpty(filePath) && File.Exists(filePath);
        }
    }
}
