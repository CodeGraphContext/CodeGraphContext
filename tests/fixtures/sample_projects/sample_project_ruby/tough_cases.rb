# Tough Case 1: Monkey Patching
# Re-opening the core String class to add a custom method.
# Static indexers must detect that 'to_slug' is now available on all strings.
class String
  def to_slug
    self.downcase.strip.gsub(' ', '-').gsub(/[^\w-]/, '')
  end
end

def test_monkey_patch
  puts "Hello World".to_slug # Should link to the definition above
end

# Tough Case 2: Singleton Classes (class << self)
# This is a common Ruby idiom for defining class methods.
class Service
  class << self
    def run_all
      puts "Running all services..."
      new.perform
    end
  end

  def perform
    puts "Performing service action"
  end
end

# Tough Case 3: Blocks, Procs, and Lambdas
# Testing scope and relationship between caller and closure.
class CallbackRegistry
  def initialize
    @callbacks = []
  end

  def register(&block)
    @callbacks << block
  end

  def execute_all(data)
    @callbacks.each { |cb| cb.call(data) }
  end
end

def test_callbacks
  registry = CallbackRegistry.new
  registry.register { |d| puts "Callback received: #{d}" }
  registry.execute_all("Secret Data")
end
