// main.typ
#import "template.typ": conf

// ==========================================
// Document Configuration
// ==========================================
#show: conf.with(
  // Project Title
  title: "Anemone Documentation",
  
  // Version
  version: "0.1",
  
  // Author
  author: "HydroGeophysics Group",
  
  // Copyright Info (Dynamic Year + Author)
  copyright: "HydroGeophysics Group, Aarhus University",
  
  // Contact Email (Optional)
  email: "hgg@geo.au.dk",
  
  // Date
  date: datetime.today(),
)

// ==========================================
// Content Sections
// ==========================================

= Introduction
This is the documentation for the **Anemone** package.

== Overview
Anemone is a high-performance tool developed by HGG.

// Example Equation
$ F(k) = integral_(-oo)^(oo) f(x) e^(-2 pi i k x) d x $

== Features
- High performance
- Easy configuration
- Robust documentation

= Installation

To install Anemone, run the following command:

