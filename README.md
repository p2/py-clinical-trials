ClinicalTrials.gov Python 3 Modules
===================================

A set of classes to be used in projects related to ClinicalTrials.gov.


Trial Data
----------

The full documentation is available at [p2.github.io/py-clinical-trials][docs].

There is a `Trial` superclass intended to represent a ClinicalTrials.gov trial.
It is designed to work off of JSON data.

The `TrialServer` class is intended to be subclassed and can be used to retrieve _Trial_ instances from a specific server.
A subclass `TrialReachServer` connecting to [TrialReach's][trialreachapi] trial API server is included.
That class also contains a _Trial_ subclass `TrialReachTrial` to facilitate working with extra data provided by TrialReach.


Docs Generation
---------------

Docs are generated with [Doxygen][] and [doxypypy][].
You will need to install doxypypy the old-fashioned way, checking out the repo and issuing `python setup.py install`, then just run Doxygen.
Running Doxygen will put the generated documentation into `docs`, the HTML files into `docs/html`.
Those files make up the content of the `gh-pages` branch.
I usually perform a second checkout of the _gh-pages_ branch and copy the html files over, with:

```sh
doxygen
rsync -a docs/html/ ../py-clinical-trials-web/
```


[docs]: https://p2.github.io/py-clinical-trials
[trialreachapi]: https://developer.trialreach.com
[doxygen]: http://www.stack.nl/~dimitri/doxygen
[doxypypy]: https://github.com/Feneric/doxypypy
