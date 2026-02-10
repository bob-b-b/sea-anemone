# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime
import os
import sys

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Anemone'
author = 'HydroGeophysics Group'
# Dynamic copyright year
copyright = f"2026–{datetime.date.today().year}, {author}"
release = '0.1'
version = release

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

master_doc = "index"

extensions = [
    'myst_parser',              # Support Markdown (.md)
    'sphinx.ext.mathjax',       # Math support
    'sphinx_markdown_tables',   # Markdown tables
    'sphinx.ext.autodoc',       # Include documentation from docstrings
    'sphinx.ext.napoleon',      # Support Google/NumPy style docstrings
    "sphinx_rtd_theme",         # Read the Docs theme
    "sphinx.ext.duration",      # Measure build duration
    "sphinx.ext.extlinks",      # Shorten external links
    "sphinx.ext.intersphinx",   # Link to other projects' documentation
    'sphinx.ext.todo',          # Support for todo items
]

templates_path = ['_templates']
exclude_patterns = []
pygments_style = 'default'

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

def setup(app):
    # Load custom CSS if you have one
    app.add_css_file('custom.css')

# ==========================================
# LaTeX Output Configuration (Professional English Layout)
# ==========================================
latex_engine = "xelatex"

# IMPORTANT: This style file must be in your root directory
latex_additional_files = ["EMDoc_style_en.sty"]

# Pass options to xcolor package to avoid conflicts
pass_options = r"\PassOptionsToPackage{dvipsnames, svgnames}{xcolor}"

# Common LaTeX packages
common_preamble = r"""
    \usepackage{amsmath}
    \usepackage{amsfonts}
    \usepackage{amssymb}
    \usepackage{titlesec} 
"""

latex_elements = {
    # Paper size and font size
    "papersize": "b4paper",
    "pointsize": "11pt",
    "passoptionstopackages": pass_options,

    # Main font settings (Times New Roman is standard for English docs)
    "fontpkg": r"\setmainfont{Times New Roman}",

    # Preamble: Input the style file and standard packages
    "preamble": common_preamble + r"""
        \input{EMDoc_style_en.sty}
        \usepackage[Bjarne]{fncychap}  % Fancy chapter headers
    """,

    # Figure alignment
    "figure_align": "H",
    
    # Page margins
    "geometry": r"\usepackage[top=3.0cm, bottom=2.5cm, left=2.5cm, right=2.5cm]{geometry}",

    # Customized Table of Contents (Includes Figures and Tables lists)
    "tableofcontents": r'''
        \pdfbookmark[0]{\contentsname}{contents}
        \tableofcontents
        \cleardoublepage
        \pdfbookmark[0]{\listfigurename}{lof}
        \listoffigures
        \cleardoublepage
        \pdfbookmark[0]{\listtablename}{lot}
        \listoftables
        \cleardoublepage
    ''',

    # Sphinx code block styling
    "sphinxsetup": r'VerbatimColor = {named}{Lavender}, VerbatimBorderColor = {named}{Silver}',
    
    # Disable default Sphinx fncychap to use the one in preamble if needed
    "fncychap": "\\usepackage[Bjarne]{fncychap}", 
    
    # Language settings
    "babel": "\\usepackage[english]{babel}",
    
    # Use custom maketitle defined in the .sty file
    "maketitle": "\\maketitle",
}

# Grouping the document tree into LaTeX files. List of tuples:
# (source start file, target name, title, author, documentclass)
latex_documents = [
    (master_doc, "Anemone.tex", project, author, "manual")
]

# Numbering settings for figures, tables, etc.
numfig = True
numfig_secnum_depth = 1
numfig_format = {
    'figure': 'Fig. %s',
    'table': 'Table %s',
    'code-block': 'Listing %s',
    'section': 'Section %s',
    'math': 'Eq. %s'
}

# Math configuration for Myst/Markdown
myst_enable_extensions = ["amsmath", "dollarmath"]
math_number_all = True
math_numfig = True