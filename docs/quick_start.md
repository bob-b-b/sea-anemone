# quick start

## Installation

### Pre-requisites

before installing anemone, the following pre-requisites are needed:

1. python, 3.9 or newer.
2. pytorch

We recommend installing pytorch from their page:

[https://pytorch.org/get-started/locally/](https://pytorch.org/get-started/locally/)

### Installation

navigate into the *anemone* folder from the console and enter the following command:

```console
pip install -e .
```


## Usage

The following is a bare bones example to compute a TEM forward.
A detailed walk-through of this example is provided on the [usage page](usage.md).

```python
from anemone.forwards import Forward
from anemone.experiment import Loop, Receiver, Waveform
import torch

tx = Loop.square(40)
rx = Receiver() # by default located at x,y,z=(0,0,0)
wv = Waveform.example()# trapezoidal example

t = torch.logspace(-5, -3, 32)

fwr = Forward(tx, rx, t, waveform=wv)

rho   = torch.tensor([40., 80., 40.])
thick = torch.tensor([20., 30.])

dbdt = fwr(rho, thick)
```



