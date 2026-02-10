# Anemone Documentation

> - Anemone is an open source electromagnetics simulator for 1-dimensional earth models.
Anemone is built with [pytorch](https://pytorch.org/), allowing for highly-parallel forward simulations leveraging GPUs.
> - A priority for anemone is flexibility and readability.

## Install sphinx and typst dependencies
### Using conda (mamba)
We recommend using conda (or mamba) to create an isolated environment for building the documentation. Mamba is a faster alternative to conda. The download and installation instructions for mamba can be found [here](https://mamba.readthedocs.io/en/latest/).

```shell
conda create -n doc python=3.11 -y
conda activate doc
pip install sphinx_rtd_theme sphinxcontrib-mermaid sphinxcontrib-bibtex sphinx sphinx-intl typst
# make latexpdf
# make html
# make epub
```

## Install essential fonts for PDF generation
```shell
sudo mkdir -p /usr/share/fonts/opentype/adobe
# 下载思源宋体 (Serif)
wget https://github.com/adobe-fonts/source-han-serif/releases/download/2.003R/09_SourceHanSerifSC.zip

# 下载思源黑体 (Sans)
wget https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSans.ttc.zip

# 解压
unzip 09_SourceHanSerifSC.zip
unzip SourceHanSans.ttc.zip

# 移动到系统字体目录
sudo mv SourceHanSans.ttc /usr/share/fonts/opentype/adobe/

# 进入你解压出的 OTF 目录
cd ~/Downloads/OTF/SimplifiedChinese/
sudo mv *.otf /usr/share/fonts/opentype/adobe/

# 刷新字体缓存
sudo fc-cache -fv

fc-list | grep "Source Han"
```

## compile translation files
```shell
make gettext
make init-en
make html-en
```

## Compile all files
```shell
make clean
make all
```
