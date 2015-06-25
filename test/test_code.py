from finline import inline


@inline
def weird_increment(x, y):
    y /= 10
    return x + y


def example_function():
    nIterations = 1000
    value = 0
    for i in xrange(nIterations):
        value += weird_increment(value, i)
    return value

import dis
dis.dis(example_function)
