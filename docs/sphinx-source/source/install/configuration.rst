Installation & Configuration
============================

This section guides you through the installation process for **Anemone**. Since Anemone leverages **PyTorch** for GPU acceleration, setting up the correct environment is crucial for optimal performance.

Prerequisites
-------------

Before installing Anemone, ensure your system meets the following requirements:

* **Operating System**: Linux (Recommended), Windows, or macOS.
* **Python**: Version 3.8 or higher.
* **Package Manager**: ``pip`` or ``conda``.

.. note::
   While Anemone can run on a CPU, using an NVIDIA GPU with CUDA support is highly recommended for large-scale forward modeling and inversion.

Step 1: Install PyTorch
-----------------------

Anemone depends on PyTorch. To ensure you get the version that matches your hardware (specifically your CUDA version), please install PyTorch **before** installing Anemone.

Visit the `PyTorch Get Started <https://pytorch.org/get-started/locally/>`_ page to generate the install command for your system.

**Example (Linux with CUDA 11.8):**

.. code-block:: bash

   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

**Example (CPU Only):**

.. code-block:: bash

   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

Step 2: Install Anemone
-----------------------

You can install Anemone directly from the source code. This is recommended to get the latest features and bug fixes.

Option A: Standard Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you just want to use the package:

.. code-block:: bash

   git clone https://github.com/HGG/anemone.git
   cd anemone
   pip install .

Option B: Developer Installation (Editable)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you plan to modify the code or contribute to Anemone, install it in **editable mode**. This allows changes in the source code to be immediately reflected without re-installing.

.. code-block:: bash

   git clone https://github.com/HGG/anemone.git
   cd anemone
   pip install -e .

Step 3: Verify Installation
---------------------------

To verify that Anemone is correctly installed and can access your GPU (if available), run the following Python snippet:

.. code-block:: python

   import torch
   import anemone

   print(f"Anemone Version: {anemone.__version__}")
   print(f"PyTorch Version: {torch.__version__}")
   
   if torch.cuda.is_available():
       print(f"GPU Detected: {torch.cuda.get_device_name(0)}")
   else:
       print("Warning: No GPU detected. Simulations will run on CPU.")

Troubleshooting
---------------

**Issue: "Module not found"**
    Ensure you are in the correct virtual environment (conda env or venv) where Anemone was installed.

**Issue: CUDA errors**
    Check that your NVIDIA drivers are up to date and that the PyTorch version installed matches your CUDA version. You can check your CUDA version with ``nvidia-smi``.