require_relative 'class_example'
require_relative 'inheritance_example'
require_relative 'module_example'
require_relative 'mixins_example'

puts "=== Ruby Sample Project ==="

greeter = Greeter.new("Name")
puts greeter.greet

dog = Dog.new("Rex")
puts dog.speak

include MathTools
puts "Square of 4: #{square(4)}"
