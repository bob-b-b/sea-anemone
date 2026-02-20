.PHONY: all html pdf-latex pdf-typst clean

# --------------------------
# Sphinx (HTML & LaTeX)
# --------------------------

# 1. Generate HTML documentation
html:
	cd sphinx-source && make html

# 2. Generate PDF via LaTeX (requires basictex/texlive)
pdf-latex:
	cd sphinx-source && make latexpdf

# --------------------------
# Typst (PDF)
# --------------------------

# 3. Generate PDF via Typst
# --root .. sets the project root one level up, allowing access to assets/images
pdf-typst:
	mkdir -p build
	cd typst-source && typst compile main.typ ../build/Anemone_Documentation.pdf --root ..

# --------------------------
# Build All / Clean
# --------------------------

# Build everything
all: html pdf-latex pdf-typst

# Clean build artifacts
clean:
	rm -rf build
	cd sphinx-source && make clean