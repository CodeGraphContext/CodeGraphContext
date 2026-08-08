namespace ToughCases
{
    public partial class MultiPartClass
    {
        // This is the implementation of the partial method from the other file
        partial void PartialDefinition()
        {
            System.Console.WriteLine("Partial definition implemented in Part B");
        }

        public void MethodFromPartB()
        {
            System.Console.WriteLine("Method in Part B called");
            PartialDefinition();
        }
    }
}
