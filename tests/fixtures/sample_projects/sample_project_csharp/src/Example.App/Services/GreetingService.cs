using System;
using Example.App.Models;

namespace Example.App.Services
{
    /// <summary>
    /// Implementation of greeting service
    /// </summary>
    public class GreetingService : IGreetingService
    {
        private readonly string _defaultGreeting = "Hello";
        
        public GreetingService()
        {
        }
        
        public GreetingService(string defaultGreeting)
        {
            _defaultGreeting = defaultGreeting;
        }
        
        public string Greet(User user)
        {
            if (user == null)
            {
                throw new ArgumentNullException(nameof(user));
            }
            
            return FormatGreeting(user);
        }
        
        private string FormatGreeting(User user)
        {
            string rolePrefix = GetRolePrefix(user.Role);
            return $"{_defaultGreeting}, {rolePrefix}{user.Name}!";
        }
        
        private string GetRolePrefix(Role role)
        {
            return role switch
            {
                Role.Admin => "Administrator ",
                Role.SuperAdmin => "Super Admin ",
                Role.User => "",
                Role.Guest => "Guest ",
                _ => ""
            };
        }
    }
}
