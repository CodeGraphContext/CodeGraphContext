require 'minitest/autorun'
require_relative '../class_example'

class TestGreeter < Minitest::Test
  def test_greet
    g = Greeter.new("World")
    assert_equal "Hello, World!", g.greet
  end
end
