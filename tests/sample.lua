-- ============================================================
-- Example Lua module: a simple Vector2 class
-- This file is used to demonstrate the lua-minifier tool.
-- ============================================================

-- Vector2 module
local Vector2 = {}
Vector2.__index = Vector2

--- Create a new Vector2
-- @param x number  X component
-- @param y number  Y component
function Vector2.new(x, y)
    local self = setmetatable({}, Vector2)
    self.x = x or 0.0
    self.y = y or 0.0
    return self
end

--- Add two vectors
function Vector2.__add(a, b)
    return Vector2.new(a.x + b.x, a.y + b.y)
end

--- Subtract two vectors
function Vector2.__sub(a, b)
    return Vector2.new(a.x - b.x, a.y - b.y)
end

--- Multiply vector by scalar
function Vector2.__mul(v, scalar)
    return Vector2.new(v.x * scalar, v.y * scalar)
end

--- Get vector magnitude
function Vector2:magnitude()
    return math.sqrt(self.x * self.x + self.y * self.y)
end

--- Normalize the vector
function Vector2:normalize()
    local mag = self:magnitude()
    if mag == 0 then
        return Vector2.new(0, 0)
    end
    return Vector2.new(self.x / mag, self.y / mag)
end

--- Dot product
function Vector2:dot(other)
    return self.x * other.x + self.y * other.y
end

--- Convert to string representation
function Vector2:__tostring()
    return string.format("Vector2(%g, %g)", self.x, self.y)
end

-- ── Utility functions ──────────────────────────────────────

--- Clamp a number between min and max values
local function clamp(value, minVal, maxVal)
    if value < minVal then
        return minVal
    elseif value > maxVal then
        return maxVal
    else
        return value
    end
end

--- Lerp between two vectors
local function lerpVectors(a, b, t)
    local clampedT = clamp(t, 0.0, 1.0)
    return Vector2.new(
        a.x + (b.x - a.x) * clampedT,
        a.y + (b.y - a.y) * clampedT
    )
end

-- ── Demo / test ─────────────────────────────────────────────

local function runDemo()
    local v1 = Vector2.new(3.0, 4.0)
    local v2 = Vector2.new(1.0, 2.0)

    print("v1 = " .. tostring(v1))
    print("v2 = " .. tostring(v2))
    print("v1 + v2 = " .. tostring(v1 + v2))
    print("v1 magnitude = " .. v1:magnitude())

    local normalized = v1:normalize()
    print("v1 normalized = " .. tostring(normalized))

    -- Test lerp
    for i = 0, 10 do
        local t     = i / 10
        local lerped = lerpVectors(v1, v2, t)
        print(string.format("  lerp(t=%.1f) = %s", t, tostring(lerped)))
    end

    -- Number literals demo (for minifier number tests)
    local hex     = 0x00FF
    local bignum  = 1_000_000   -- Luau separator
    local sci     = 1.5e+02
    local leading = 0.75

    print("hex=" .. hex .. " bignum=" .. bignum .. " sci=" .. sci)

    -- Long string
    local message = [[
This is a multi-line
long string in Lua.
It spans several lines.
]]
    print(message)
end

runDemo()

return Vector2
