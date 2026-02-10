using Example.App.Models;

namespace Example.App.Services
{
    /// <summary>
    /// Interface for greeting services
    /// </summary>
    public interface IGreetingService
    {
        string Greet(User user);
    }
}
