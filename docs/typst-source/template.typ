// template.typ

// ==========================================
// Helper Functions
// ==========================================

// A simple block for quotes or notes
#let md-quote(body) = block(
  fill: rgb("#f3e5f5"),
  stroke: (left: 4pt + rgb("#9c27b0")),
  inset: (x: 12pt, y: 10pt),
  radius: 2pt,
  width: 100%,
  spacing: 1.0em,
  body
)

// Bold label helper
#let label(body) = par(first-line-indent: 0pt)[*#body*]

// ==========================================
// Main Configuration Function
// ==========================================
#let conf(
  title: "",
  version: "",
  author: "",
  copyright: "",
  email: "",
  date: datetime.today(),
  doc
) = {

  // 1. Global Font Settings
  // Using Times New Roman for a professional scientific look
  set text(
    font: "Times New Roman",
    size: 11pt, // 11pt is standard for readable English docs
    lang: "en",
    region: "us"
  )
  
  // Paragraph Settings: Mimic LaTeX's compact typesetting
  set par(
    first-line-indent: 2em,
    justify: true,
    leading: 0.8em, // Tighter line spacing
    spacing: 1.0em  // Paragraph spacing
  )

  // 2. Page Settings (A4 with specific margins)
  set page(
    paper: "a4",
    margin: (top: 3cm, bottom: 2.5cm, x: 2.5cm),
    numbering: "1",
  )

  // 3. Heading Numbering
  set heading(numbering: "1.1")
  set math.equation(numbering: "(1.1)")

  // Figure Supplements (Prefixes)
  show figure.where(kind: image): set figure(supplement: "Fig.")
  show figure.where(kind: table): set figure(supplement: "Table")

  // 4. Heading Styling (Serif Bold)
  // Level 1 Heading (Part/Chapter style)
  show heading.where(level: 1): it => {
    set align(center)
    set text(size: 16pt, weight: "bold")
    pagebreak(weak: true)
    v(2em)
    if it.numbering != none {
      text(size: 14pt, weight: "bold")[Part #counter(heading).display()]
      parbreak()
    }
    it.body
    v(1.5em)
  }
  
  // Level 2 Heading (Section)
  show heading.where(level: 2): it => {
    set align(left)
    set text(size: 14pt, weight: "bold") 
    v(1em)
    it
    v(0.6em)
  }

  // Level 3 Heading (Subsection)
  show heading.where(level: 3): it => {
    set align(left)
    set text(size: 12pt, weight: "bold")
    v(0.6em)
    it
    v(0.4em)
  }

  // Link Styling
  show link: set text(fill: rgb("#0000FF")) 

  // List Styling
  set list(indent: 2em, spacing: 0.6em, marker: ([•], [‣], [⁃]))
  set enum(indent: 2em, spacing: 0.6em)

  // Code Block Styling (Refined)
  show raw.where(block: true): block.with(
    fill: luma(98%), 
    stroke: 0.5pt + rgb("#a0a0a0"), // Thin gray border
    width: 100%,
    inset: 8pt,
    radius: 2pt,
  )

  // Code Font Settings
  show raw: set text(
    font: ("DejaVu Sans Mono", "Courier New"), 
    size: 9pt, // Slightly smaller than body text
    weight: "regular" 
  )

  // Caption Styling
  show figure.caption: set text(size: 10pt, weight: "bold")

  // ====================
  // Cover Page
  // ====================
  if title != "" {
    set page(numbering: none)
    align(center + horizon)[
      #v(-3cm)
      // Title
      #text(size: 30pt, weight: "bold")[#title]
      #v(0.5cm)
      // Version
      #text(size: 18pt)[v#version]
      #v(2cm)
      
      // Author / Email
      #text(size: 15pt)[
        #if email != "" {
            link("mailto:" + email)[#author]
        } else {
            author
        }
      ]
      #v(1cm)
      
      // Copyright
      #text(size: 15pt)[#copyright]
      #v(2cm)
      
      // Date
      #text(size: 14pt)[
        #date.display("[month repr:long] [day], [year]")
      ]
    ]
    pagebreak()
  }

  // ====================
  // Table of Contents (Two Columns)
  // ====================
  set page(numbering: "i") 
  show link: set text(fill: black) // TOC links should be black

  align(center)[ #text(size: 16pt, weight: "bold")[Table of Contents] ]
  v(1em)

  // TOC Entry Styling
  show outline.entry.where(level: 1): it => {
    v(0.5em, weak: true)
    set text(weight: "bold", size: 11pt, fill: black)
    block[
      #link(it.element.location())[
        #if it.element.numbering != none {
            numbering(it.element.numbering, ..counter(heading).at(it.element.location()))
            h(0.5em)
        }
        #it.element.body
        #box(width: 1fr, repeat[.])
        #counter(page).at(it.element.location()).first()
      ]
    ]
  }

  show outline.entry.where(level: 2): it => {
    set text(size: 11pt, fill: black)
    block[
      #link(it.element.location())[
        #if it.element.numbering != none {
            numbering(it.element.numbering, ..counter(heading).at(it.element.location()))
            h(0.5em)
        }
        #it.element.body
      ]
      #box(width: 1fr, repeat[.])
      #link(it.element.location())[
        #counter(page).at(it.element.location()).first()
      ]
    ]
  }
  
  // Hide level 3 from TOC for brevity
  show outline.entry.where(level: 3): it => {}

  columns(2)[
    #set text(size: 10pt) 
    #set par(leading: 0.7em)
    #outline(title: none, indent: auto)
  ]
  pagebreak()

  // ====================
  // List of Figures
  // ====================
  align(center)[ #text(size: 16pt, weight: "bold")[List of Figures] ]
  v(1em)
  
  // General outline entry styling for figures and tables
  show outline.entry: it => {
    set text(size: 11pt, fill: black)
    let caption-text = if it.element.has("caption") { it.element.caption.body } else { it.element.body }
    block[
      #link(it.element.location())[
        #if it.element.numbering != none [
          #it.element.supplement
          #numbering(it.element.numbering, ..counter(figure.where(kind: it.element.kind)).at(it.element.location())):
        ]
        #h(0.5em)
        #caption-text
      ]
      #box(width: 1fr, repeat[.])
      #link(it.element.location())[ #counter(page).at(it.element.location()).first() ]
    ]
  }

  columns(1)[
    #set text(size: 11pt)
    #set par(leading: 0.8em)
    #outline(title: none, target: figure.where(kind: image))
  ]
  pagebreak()

  // ====================
  // List of Tables
  // ====================
  align(center)[ #text(size: 16pt, weight: "bold")[List of Tables] ]
  v(1em)
  columns(1)[
    #set text(size: 11pt)
    #set par(leading: 0.8em)
    #outline(title: none, target: figure.where(kind: table), indent: auto)
  ]
  pagebreak()

  // ====================
  // Main Content Start
  // ====================
  set page(numbering: "1") 
  show link: set text(fill: blue)
  counter(page).update(1)  
  doc
}