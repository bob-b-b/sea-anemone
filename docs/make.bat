@ECHO OFF

REM Command parsing
if "%1" == "" goto help
if "%1" == "html" goto html
if "%1" == "pdf-latex" goto pdflatex
if "%1" == "pdf-typst" goto pdftypst
if "%1" == "all" goto all
if "%1" == "clean" goto clean

:help
echo.
echo Please use `make ^<target^>` where ^<target^> is one of
echo   html       to make standalone HTML files
echo   pdf-latex  to make LaTeX files and run them through pdflatex
echo   pdf-typst  to make PDF files using Typst
echo   all        to build all formats
echo   clean      to clean build directories
goto end

:html
echo Building HTML...
pushd sphinx-source
call make.bat html
popd
goto end

:pdflatex
echo Building PDF (LaTeX)...
pushd sphinx-source
call make.bat latexpdf
popd
goto end

:pdftypst
echo Building PDF (Typst)...
if not exist build mkdir build
REM Compiling Typst file. We assume we are in the project root.
typst compile typst-source\main.typ build\Anemone_Documentation.pdf --root .
goto end

:all
echo Building ALL...
call make.bat html
call make.bat pdf-latex
call make.bat pdf-typst
goto end

:clean
echo Cleaning build directories...
if exist build rmdir /s /q build
pushd sphinx-source
call make.bat clean
popd
goto end

:end