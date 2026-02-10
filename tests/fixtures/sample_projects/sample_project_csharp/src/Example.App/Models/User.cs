namespace Example.App.Models
{
    /// <summary>
    /// Represents a user in the system
    /// </summary>
    public class User
    {
        public string Name { get; set; }
        public Role Role { get; set; }
        
        public User(string name, Role role)
        {
            Name = name;
            Role = role;
        }
        
        public string GetDisplayName()
        {
            return $"{Name} ({Role})";
        }
    }
}
