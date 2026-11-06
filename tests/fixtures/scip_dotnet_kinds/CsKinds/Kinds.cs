using System;

namespace Fx
{
    public delegate int Op(int a);

    public interface IShape
    {
        double Area();
    }

    public struct Point
    {
        public int X;
        public Point(int x) { X = x; }
        public static Point Origin() { return new Point(0); }
    }

    public enum Color { Red, Green }

    public record Rec(int A);

    public static class Ext
    {
        public static int Twice(this int v) { return v * 2; }
    }

    public class Calc : IShape
    {
        public const int K = 1;
        public static int Counter;
        public int field;
        public int Prop { get; set; }
        public event EventHandler Changed;

        static Calc() { Counter = 0; }
        public Calc() { }
        public Calc(int x) { field = x; }

        public double Area() { return 0; }
        public static int Add(int a, int b) { return a + b; }
        public void M() { }
        public void M(int x) { }

        public void Run()
        {
            var c = new Calc(1);
            M(); M(2);
            Add(1, 2);
            var t = 3.Twice();
            var p = Point.Origin();
            string s = "🚀"; Add(3, 4);
            string u = "é"; Add(5, 6);
            string w = "🚀🚀"; M(7);
        }
    }
}
