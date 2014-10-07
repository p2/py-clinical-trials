ClinicalTrials.gov Python 3 Modules
===================================

A set of classes to be used in projects related to ClinicalTrials.gov.


Trial Data
----------

The full documentation is available at [p2.github.io/py-clinical-trials][docs].

There is a `Trial` superclass intended to represent a ClinicalTrials.gov trial.
It is designed to work off of JSON data.

The `TrialServer` class is intended to be subclassed and can be used to retrieve _Trial_ instances from a specific server.
A subclass `LillyV2Server` connecting to [LillyCOI's v2][lillycoi] trial API server is included.
That class also contains a _Trial_ subclass `LillyTrial` to facilitate working with extra data provided by Lilly.


Docs Generation
---------------

Docs are generated with [Doxygen][] and [doxypypy][].
You will need to install doxypypy the old-fashioned way, checking out the repo and issuing `python setup.py install`, then just run Doxygen:

```sh
doxygen
```


[docs]: https://p2.github.io/py-clinical-trials
[lillycoi]: https://developer.lillycoi.com
[doxygen]: http://www.stack.nl/~dimitri/doxygen
[doxypypy]: https://github.com/Feneric/doxypypy
