using System;

namespace Example.App.Models
{
    /// <summary>
    /// Struct for representing a 2D point
    /// </summary>
    public struct Point
    {
        public double X { get; set; }
        public double Y { get; set; }
        
        public Point(double x, double y)
        {
            X = x;
            Y = y;
        }
        
        public double DistanceFromOrigin()
        {
            return Math.Sqrt(X * X + Y * Y);
        }
        
        public static Point operator +(Point a, Point b)
        {
            return new Point(a.X + b.X, a.Y + b.Y);
        }
        
        public override string ToString()
        {
            return $"({X}, {Y})";
        }
    }
    
    /// <summary>
    /// Readonly struct for immutable coordinates
    /// </summary>
    public readonly struct Coordinate
    {
        public double Latitude { get; }
        public double Longitude { get; }
        
        public Coordinate(double latitude, double longitude)
        {
            Latitude = latitude;
            Longitude = longitude;
        }
        
        public override string ToString()
        {
            return $"Lat: {Latitude}, Lon: {Longitude}";
        }
    }
}
