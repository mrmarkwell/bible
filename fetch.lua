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


-- --- 2. ESV API Optional Parameters ---
-- You can change these values to customize the output from the API.

-- (boolean) Include a line at the beginning of each passage indicating the book, chapter, and verse range.
local include_passage_references = false
-- (boolean) Include verse numbers in the text.
local include_verse_numbers = false
-- (boolean) Include the verse number for the first verse of each passage.
local include_first_verse_numbers = false
-- (boolean) Include footnote markers and the text of the footnotes.
local include_footnotes = false
-- (boolean) Include the body of the footnotes.
local include_footnote_body = false
-- (boolean) Include section headings.
local include_headings = false
-- (boolean) Include a short copyright notice.
local include_short_copyright = false
-- (boolean) Include the full copyright notice.
local include_copyright = false
-- (boolean) Include a horizontal line at the beginning of each passage.
local include_passage_horizontal_lines = false
-- (boolean) Include a horizontal line above each section heading.
local include_heading_horizontal_lines = false
-- (integer) The number of '=' characters to use for horizontal lines.
local horizontal_line_length = 5
-- (boolean) Include the word "Selah."
local include_selahs = false
-- (string: 'space' or 'tab') The character to use for indentation.
local indent_using = 'space'
-- (integer) The number of indentation characters for the first line of each paragraph.
local indent_paragraphs = 2
-- (boolean) Indent lines of poetry.
local indent_poetry = true
-- (integer) The number of indentation characters for each line of poetry.
local indent_poetry_lines = 4
-- (integer) The number of indentation characters for "The word of the Lord" and similar phrases.
local indent_declares = 2
-- (integer) The number of indentation characters for the doxology at the end of each book of Psalms.
local indent_psalm_doxology = 1

-- --- 3. Read Command-Line Arguments ---
-- The 'arg' table holds command-line arguments. arg[1] is the first argument after the script name.
if not arg[1] then
  print("Usage: lua fetch.lua \"<bible reference>\"")
  print("Example: lua fetch.lua \"John 3:16-17\"")
  os.exit(1)
end
local verseReference = arg[1]

-- --- 4. Read API Key from Environment Variable ---
local apiKey = os.getenv("ESV_API_KEY")
if not apiKey then
  io.stderr:write("Error: ESV_API_KEY environment variable not set.\n")
  io.stderr:write("Please get a key from https://api.esv.org/ and set the variable.\n")
  os.exit(1)
end

-- --- 5. Construct the API Request ---
local apiBaseURL = "https://api.esv.org/v3/passage/text/"

-- We need to manually URL-encode the query parameter.
local function url_encode(str)
  str = string.gsub(str, "([^%w%.%-%_])", function(c) return string.format("%%%02X", string.byte(c)) end)
  return str
end

-- A table to hold all the parameters for the API call.
local params = {
  q = verseReference,
  ['include-passage-references'] = tostring(include_passage_references),
  ['include-verse-numbers'] = tostring(include_verse_numbers),
  ['include-first-verse-numbers'] = tostring(include_first_verse_numbers),
  ['include-footnotes'] = tostring(include_footnotes),
  ['include-footnote-body'] = tostring(include_footnote_body),
  ['include-headings'] = tostring(include_headings),
  ['include-short-copyright'] = tostring(include_short_copyright),
  ['include-copyright'] = tostring(include_copyright),
  ['include-passage-horizontal-lines'] = tostring(include_passage_horizontal_lines),
  ['include-heading-horizontal-lines'] = tostring(include_heading_horizontal_lines),
  ['horizontal-line-length'] = tostring(horizontal_line_length),
  ['include-selahs'] = tostring(include_selahs),
  ['indent-using'] = indent_using,
  ['indent-paragraphs'] = tostring(indent_paragraphs),
  ['indent-poetry'] = tostring(indent_poetry),
  ['indent-poetry-lines'] = tostring(indent_poetry_lines),
  ['indent-declares'] = tostring(indent_declares),
  ['indent-psalm-doxology'] = tostring(indent_psalm_doxology),
}

-- Build the query string from the params table.
local query_parts = {}
for key, value in pairs(params) do
  table.insert(query_parts, url_encode(key) .. "=" .. url_encode(value))
end
local query_string = table.concat(query_parts, "&")
local fullURL = apiBaseURL .. "?" .. query_string

print("Fetching: " .. verseReference)

-- --- 6. Execute the Request ---
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

-- --- 7. Parse the JSON Response ---
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


-- --- 8. Display the Result ---
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
