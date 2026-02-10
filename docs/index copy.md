# Welcome to anemone

Would you like to run transient electromagnetic simulations in python like this:
```python
dbdt = fwr(resistivity, thickness)
```
With a few lines of setup particular to your instrumentation, it can be that easy.

## Intro

Anemone is an open source electromagnetics simulator for 1-dimensional earth models.
Anemone is built with [pytorch](https://pytorch.org/), allowing for highly-parallel forward simulations leveraging GPUs.

A priority for anemone is flexibility and readability.

As with many other 1d EM codes, [Ward and Hohmann 1988](https://doi.org/10.1190/1.9781560802631.ch4
) is an indispensable reference. 
Where relevant, references to the W&H are included in the doc-strings of functions. The same is true for equations from other papers listed below.


## Key References

Stanley H. Ward and Gerald W. Hohmann, (1988), "4. Electromagnetic Theory for Geophysical Applications," Investigations in Geophysics : 130-311. [https://doi.org/10.1190/1.9781560802631.ch4](https://doi.org/10.1190/1.9781560802631.ch4)

Christensen, N.B. (1990), Optimized fast hankel transform filters. Geophysical Prospecting, 38: 545-568. [https://doi.org/10.1111/j.1365-2478.1990.tb01861.x](https://doi.org/10.1111/j.1365-2478.1990.tb01861.x)

Johansen, H.K. and Sørensen, K. (1979), Fast Hankel Transforms. Geophysical Prospecting, 27: 876-901. [https://doi.org/10.1111/j.1365-2478.1979.tb01005.x](https://doi.org/10.1111/j.1365-2478.1979.tb01005.x)

D. E. Boerner and G. F. West, (1984), Efficient calculation of the electromagnetic fields of an extended source. GEOPHYSICS 49: 2057-2060.
[https://doi.org/10.1190/1.1441618](https://doi.org/10.1190/1.1441618)

Stehfest, H. (1970), Algorithm 368 Numerical inversion of Laplace transforms. Association for Computing Machinery (ACM), [https://doi.org/10.1145/361953.361969](https://dl.acm.org/doi/10.1145/361953.361969)