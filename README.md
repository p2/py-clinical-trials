ClinicalTrials.gov Python 3 Modules
===================================

A set of classes to be used in projects related to ClinicalTrials.gov.


Trial Data
----------

There is a `Trial` superclass intended to represent a ClinicalTrials.gov trial.
It is designed to work off of JSON data.

The `TrialServer` class is intended to be subclassed and can be used to retrieve _Trial_ instances from a specific server.
A subclass connecting to [LillyCOI's v2][lillycoi] trial API server is included.
That class also contains a _Trial_ subclass `LillyTrial` to facilitate working with extra data provided by Lilly.

[lillycoi]: https://developer.lillycoi.com
