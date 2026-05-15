local Rectangle = require("rectangle")
local Utils = require("utils")

local function main()
    Utils.log(Utils.greet("CGC"))
    
    local r = Rectangle.new(10, 20)
    Utils.log("Area: " .. r:area())
end

main()
