# Make `tests` a REGULAR package (fix-coherence-container-contract /
# add-framework-ci-pipeline, audit finding F12): a regular package anywhere on
# sys.path beats a namespace package regardless of position, so without this
# file any environment with an installed third-party `tests` package
# (e.g. the `tests` pypi package) shadows this directory and the five
# conformance files silently fail collection with
# "No module named 'tests.fixtures.coherence'".
