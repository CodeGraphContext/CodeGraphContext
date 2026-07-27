-- Tough Case 1: Prototype-based Inheritance via Metatables
-- This is how Lua "simulates" classes.
local Base = {}
Base.__index = Base

function Base:new(name)
    local obj = setmetatable({}, self)
    obj.name = name
    return obj
end

function Base:describe()
    return "Base: " .. self.name
end

local Extended = setmetatable({}, Base)
Extended.__index = Extended

function Extended:describe()
    -- Calling "super" method via explicit table access
    return "Extended: " .. Base.describe(self)
end

-- Tough Case 2: Modules and Require
-- Testing if the indexer handles the return value of require.
local math_utils = {}
function math_utils.add(a, b) return a + b end

-- Tough Case 3: Closures and Private State
-- Using a function factory to create objects with private variables.
local function create_counter()
    local count = 0
    return {
        increment = function()
            count = count + 1
            return count
        end,
        get = function() return count end
    }
end

local c = create_counter()
c.increment()

-- Tough Case 4: Variadic Functions and Unpacking
local function variadic(...)
    local args = {...}
    print("Received " .. #args .. " arguments")
end
