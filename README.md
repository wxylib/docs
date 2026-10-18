# wxylib/docs

The source of the wxylib site, **https://wxylib.github.io/docs/**: one
place for what wxylib is, what works, how-tos, explainers, the design
documents and how to help.

wxylib is an early-stage set of Rust crates that takes the modular ideas
inside GDAL (grids, georeferencing, chunked reads, warping, virtual
datasets), gives each one its own small home, and builds on existing
crates (async-tiff, zarrs, Icechunk, rwarp) rather than replacing them.
GDAL is the inspiration and, for now, the test oracle.

![The R0 to R6 raster-vector spectrum, with R1 to R3 warped today, R3' modelled, R4 to R6 planned](img/spectrum.svg)

## Reading on GitHub

Every page is markdown and reads here too:

- [Start here](start.qmd): run `wxy` from a container or build it.
- [Capability map](capabilities/map.html) (open the rendered site to view it).
- [How-tos](vignettes/README.md), starting from the
  [OISST walk-through](oisst-virtual.md).
- [Explainers](explainers/index.qmd): how each ported GDAL mechanism works
  and how it is checked.
- [Gaps and contributing](contribute.qmd).
- [Design documents](https://github.com/wxylib/design).

## Building the site

The site is a [Quarto](https://quarto.org) website. The design documents
are pulled in from wxylib/design at build time, so they have one copy.

```sh
git clone https://github.com/wxylib/design   # into this directory, as design/
quarto preview
```

`.github/workflows/publish.yml` renders on every pull request and
publishes from main.

License: MIT OR Apache-2.0.
