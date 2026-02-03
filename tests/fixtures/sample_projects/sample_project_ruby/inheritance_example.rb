class Animal
  def initialize(name)
    @name = name
  end

  def speak
    "#{@name} makes a sound."
  end
end

class Dog < Animal
  def speak
    "#{@name} barks!"
  end
end
