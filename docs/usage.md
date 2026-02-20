## Example 1 (quick-start)
Let's walk-through the example we saw in the [quick start](quick_start.md).


### The imports

```python
from anemone.experiment import Loop, Receiver, Waveform
from anemone.forwards import Forward
import torch
```

- The main user configurable bits are included in the anemone.experiment module. 
- The forward module contains operators that take the users defined configuration and returns a function that computes $dB/dt$ based on resistivity and thickness.
- torch is required for tensors (or arrays), for example the set of times for which $dB/dt$ is evaluated, or the resistivity values in the 1d earth.

### The configuration

```python
tx = Loop.square(40)
rx = Receiver() # by default located at x,y,z=(0,0,0)
wv = Waveform.example()# trapezoidal example

t = torch.logspace(-5, -3, 32)

fwr = Forward(tx, rx, t, waveform=wv)
```

In this example, we have defined the following TEM system:
- a 40m x 40m transmit loop
- a unit dipole receiver placed at the origin
- trapezoidal example waveform
- set of times at which $dB/dt$ is evaluated.

The forward operator takes these configuration parameters and return the function for follow-up simulations of the $dB/dt$ response.

### Running a forward

Now, running the forward is relatively simple:

```python
rho   = torch.tensor([40., 80., 40.])
thick = torch.tensor([20., 30.])

dbdt = fwr(rho, thick)
```

We define our resistivity values in the layers and the associated thicknesses (last layer extends to infinity) and we can pass these tensors to the forward function to get the response.
We've used 3 layers in the example, but an arbitrary number can used.

### Running multiple forwards

Instead of the single $dB/dt$ response, multiple can be obtained in one function call. The important thing is that the **layers** are indexed along the 0-th dimension:

```python
rho = torch.ones((3,10))*40
rho[1, :] = torch.linspace(30, 80, 10) # sweep the middle layer

thick = torch.ones((2,10))*20.
thick[1,:] = 30

dbdts = fwr(rho, thick)
```