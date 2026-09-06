// This file defines the style of your generated image.

// This variable will be set by the Lua script via the `--input` flag.
#let verse_text = "Testing testing 123"

// --- Page and Text Styling ---
// You can change fonts, sizes, and colors here.
#set page(width: 4000pt, height: 3000pt, fill: black)
#set text(
  fill: white,
  font: "Maple Mono NF", // Typst is better at finding fonts by family name
  weight: "bold",
  style: "italic",
  size: 400pt
)

// --- Content Layout ---
// This aligns the text block to the center of the page.
#align(center + horizon)[
  // The #raw() function ensures your newlines (\n) are respected.
  #verse_text
]
