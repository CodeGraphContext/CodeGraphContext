local Utils = {}

function Utils.greet(name)
    return "Hello, " .. tostring(name)
end

function Utils.log(msg)
    print("[LOG] " .. msg)
end

return Utils
