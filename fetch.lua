--!/usr/bin/env lua

--[[
  A command-line tool to fetch a Bible passage from the ESV API using Lua.

  Dependencies:
  - LuaSocket: for making the HTTP request (luarocks install luasocket)
  - LuaSec: for HTTPS support (luarocks install luasec)
  - dkjson: for parsing the JSON response (luarocks install dkjson)

  Usage:
  1. Set your API key: export ESV_API_KEY="YOUR_KEY_HERE"
  2. Run the script:   lua fetch.lua "John 3:16"
--]]

-- --- 1. Load Required Libraries ---
-- Use pcall to safely require libraries and provide helpful error messages if they're missing.
local socket_ok, socket = pcall(require, "socket")
if not socket_ok then
  io.stderr:write("Error: LuaSocket not found.\nPlease install it with: luarocks install luasocket\n")
  os.exit(1)
end

-- Load LuaSec to handle HTTPS requests for LuaSocket.
local https_ok, https = pcall(require, "ssl.https")
if not https_ok then
  io.stderr:write("Error: LuaSec (ssl.https) not found.\nPlease install it with: luarocks install luasec\n")
  os.exit(1)
end

local json_ok, json = pcall(require, "dkjson")
if not json_ok then
  io.stderr:write("Error: dkjson not found.\nPlease install it with: luarocks install dkjson\n")
  os.exit(1)
end

-- LTN12 is part of LuaSocket and helps process response bodies.
local ltn12_ok, ltn12 = pcall(require, "ltn12")
if not ltn12_ok then
    io.stderr:write("Error: ltn12 library not found (should be part of LuaSocket).\n")
    os.exit(1)
end


-- --- 2. Read Command-Line Arguments ---
-- The 'arg' table holds command-line arguments. arg[1] is the first argument after the script name.
if not arg[1] then
  print("Usage: lua fetch.lua \"<bible reference>\"")
  print("Example: lua fetch.lua \"John 3:16-17\"")
  os.exit(1)
end
local verseReference = arg[1]

-- --- 3. Read API Key from Environment Variable ---
local apiKey = os.getenv("ESV_API_KEY")
if not apiKey then
  io.stderr:write("Error: ESV_API_KEY environment variable not set.\n")
  io.stderr:write("Please get a key from https://api.esv.org/ and set the variable.\n")
  os.exit(1)
end

-- --- 4. Construct the API Request ---
local apiBaseURL = "https://api.esv.org/v3/passage/text/"

-- We need to manually URL-encode the query parameter.
local function url_encode(str)
  str = string.gsub(str, "([^%w%.%-%_])", function(c) return string.format("%%%02X", string.byte(c)) end)
  return str
end

local fullURL = apiBaseURL .. "?q=" .. url_encode(verseReference)

print("Fetching: " .. verseReference)

-- --- 5. Execute the Request ---
local response_body_parts = {} -- This table will collect the response body chunks.

-- By requiring 'ssl.https', https.request can now handle https URLs.
-- We use a 'sink' to direct the response body into our table.
local ok, code, headers, status = https.request({
  url = fullURL,
  method = "GET",
  headers = {
    -- The ESV API requires the key in the Authorization header.
    ["Authorization"] = "Token " .. apiKey
  },
  sink = ltn12.sink.table(response_body_parts)
})

-- After the request, concatenate the parts into a single string.
local body = table.concat(response_body_parts)

-- Check for a successful request. 'ok' will be 1 on success.
if not ok then
    io.stderr:write("Error: https.request failed. Status: " .. tostring(status) .. "\n")
    os.exit(1)
end

-- Check for non-200 status codes.
if code ~= 200 then
  io.stderr:write("API returned a non-200 status code: " .. status .. "\n")
  io.stderr:write("Response: " .. (body or "No response body") .. "\n")
  os.exit(1)
end

if not body or body == "" then
    io.stderr:write("Error: Failed to get a response body from the API.\n")
    os.exit(1)
end

-- --- 6. Parse the JSON Response ---
-- Capture all 3 return values from dkjson for proper error handling.
local esvResponse, pos, err = json.decode(body)

-- Check for JSON parsing errors.
if not esvResponse then
  io.stderr:write("Error parsing JSON response: " .. tostring(err) .. " at position " .. tostring(pos) .. "\n")
  io.stderr:write("Raw Body: " .. body .. "\n")
  os.exit(1)
end

-- Add a type check to ensure the response is a table (JSON object).
if type(esvResponse) ~= "table" then
    io.stderr:write("Error: API response was not a JSON object as expected.\n")
    io.stderr:write("Decoded Type: " .. type(esvResponse) .. "\n")
    io.stderr:write("Decoded Value: " .. tostring(esvResponse) .. "\n")
    os.exit(1)
end


-- --- 7. Display the Result ---
-- Check if .passages exists before trying to get its length.
if not esvResponse.passages or #esvResponse.passages == 0 then
  io.stderr:write("Error: Passage not found for query '" .. (esvResponse.query or verseReference) .. "'.\n")
  -- The ESV API uses the 'detail' key for some errors like invalid tokens.
  if esvResponse.detail then
    io.stderr:write("API Detail: " .. esvResponse.detail .. "\n")
  end
  os.exit(1)
end

-- Join the passages together. Usually there is only one.
local fullPassage = table.concat(esvResponse.passages, "")

print("----------------------------------------")
-- The Canonical reference is the official, full reference returned by the API.
print(esvResponse.canonical .. " (ESV)\n")
-- Trim leading/trailing whitespace for cleaner output.
print(fullPassage:match("^%s*(.-)%s*$"))
print("----------------------------------------")
