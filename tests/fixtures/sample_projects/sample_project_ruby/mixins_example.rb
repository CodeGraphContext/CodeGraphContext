module Flyable
  def fly
    "#{@name} is flying!"
  end
end

class Bird
  include Flyable

  def initialize(name)
    @name = name
  end
end
