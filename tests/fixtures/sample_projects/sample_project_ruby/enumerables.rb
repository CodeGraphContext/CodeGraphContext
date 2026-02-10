numbers = [1, 2, 3, 4, 5]
squares = numbers.map { |n| n * n }
evens = numbers.select(&:even?)

puts "Squares: #{squares}"
puts "Evens: #{evens}"
