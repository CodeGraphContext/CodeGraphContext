File.open("example.txt", "w") { |f| f.puts "Hello Ruby File!" }

content = File.read("example.txt")
puts "File says: #{content}"
