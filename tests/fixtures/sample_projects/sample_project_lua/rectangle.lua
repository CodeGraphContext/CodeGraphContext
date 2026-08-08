local Rectangle = {}
Rectangle.__index = Rectangle

function Rectangle.new(w, h)
    local self = setmetatable({}, Rectangle)
    self.width = w
    self.height = h
    return self
end

function Rectangle:area()
    return self.width * self.height
end

return Rectangle
