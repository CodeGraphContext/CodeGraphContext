namespace Example.App
{
    /// <summary>
    /// Demonstrates nested classes in C#
    /// </summary>
    public class OuterClass
    {
        private string _outerValue;
        
        public OuterClass(string value)
        {
            _outerValue = value;
        }
        
        public InnerClass CreateInner(string innerValue)
        {
            return new InnerClass(this, innerValue);
        }
        
        /// <summary>
        /// Inner class that can access outer class members
        /// </summary>
        public class InnerClass
        {
            private OuterClass _outer;
            private string _innerValue;
            
            public InnerClass(OuterClass outer, string value)
            {
                _outer = outer;
                _innerValue = value;
            }
            
            public string Combine()
            {
                return $"{_outer._outerValue}-{_innerValue}";
            }
        }
    }
}
