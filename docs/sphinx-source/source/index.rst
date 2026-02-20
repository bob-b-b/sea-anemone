.. Anemone documentation master file, created by
   sphinx-quickstart.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Anemone Documentation
=====================

Welcome to the **Anemone** documentation.

Anemone is an open-source electromagnetics simulator for 1-dimensional earth models, built with **PyTorch** to leverage GPU acceleration. This documentation is designed to guide you from installation to advanced theoretical concepts and benchmarking.

.. rubric:: Documentation Guide

This manual is organized into the following main sections:

#. **Installation & Configuration**: Instructions on how to install Anemone, configure the environment, and handle dependencies.
#. **Theoretical Background**: A deep dive into the physics of Transient Electromagnetics (TEM), including forward modeling derivations, waveform analysis, and inversion logic.
#. **Usage Tutorials**: Step-by-step guides on how to run simulations, handle data, and visualize results.
#. **Benchmarks & Comparisons**: Validation scripts and performance comparisons against other industry-standard packages (`SimPEG <https://simpeg.xyz/>`_, `empymod <https://empymod.emsig.xyz/en/stable/manual/index.html>`_, `AarhusInv <https://hgg.au.dk/software/aarhusinv>`_).
#. **API Reference**: Detailed documentation of the Anemone functions and classes.

.. toctree::
   :maxdepth: 2
   :caption: Installation & Setup
   :hidden:

   install/index

.. toctree::
   :maxdepth: 2
   :caption: Theoretical Background
   :hidden:

   theory/index

.. toctree::
   :maxdepth: 2
   :caption: Usage Tutorials
   :hidden:

   tutorials/index

.. toctree::
   :maxdepth: 2
   :caption: Benchmarks
   :hidden:

   benchmarks/index

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   :hidden:

   api/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`