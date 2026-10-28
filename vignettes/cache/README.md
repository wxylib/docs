# Keep the bytes a run reads

**The question:** a remote raster is read again and again while a script
or a map is being worked on, and every run fetches the same tiles over the
network. GDAL's `/vsicurl/` cache lives in memory, inside one process, and
is gone when the process ends; keeping a local copy means choosing a
format and converting the whole file, when only a few tiles were ever
read.

**What wxylib does:** `wxy warp --cache DIR` keeps every byte range a run
fetches, still compressed as the source stored it, in a directory of
Parquet files. The next run reads from there what it holds and fetches
only the rest. Each row carries what was fetched and how to check it is
still current, so the cache is itself a small byte-reference table, with
the bytes in it, covering exactly what was read. The warp's plan reports
what is held before anything is read.

## The run

[run.py](run.py) warps a fixture COG to Antarctic polar stereographic
twice with the same cache, and prints the plan's cache summary before
each run, what each run fetched, and the rows the cache holds:

```sh
wxy warp source.tif out.zarr --crs EPSG:3031 \
  --extent -4000000 -4000000 4000000 4000000 --size 400 400 \
  -r bilinear --cache cache --dry-run      # what will be fetched
wxy warp source.tif out.zarr ... --cache cache
```

```
run 1, planned: 0 chunks held (0 bytes), 6 to fetch (109032 bytes)
run 1, done:    cache: 0 reads held (0 bytes), 7 from the source (141800 bytes)
run 2, planned: 6 chunks held (109032 bytes), 0 to fetch (0 bytes)
run 2, done:    cache: 7 reads held (141800 bytes), 0 from the source (0 bytes)
outputs identical: True
```

The plan names the six tiles the warp needs. The run makes seven reads:
the six tiles and the file's header. The second run reads nothing from
the source and writes the same output.

The cache is plain Parquet, so any tool can look in it:

```
offset  size   validator                    checked_by
0       32768  510944-1793192399505037344   size_mtime
401868  19275  510944-1793192399505037344   size_mtime
421151  19434  510944-1793192399505037344   size_mtime
...
```

Run it with a URL to see the same thing over HTTP, with the server's ETag
as the validator:

```sh
python run.py https://raw.githubusercontent.com/wxylib/fixtures/main/cog/world-int16-deflate.tif
```

## What a row holds

| Column | Holds |
|---|---|
| `source`, `offset`, `size` | the key: which bytes of which source |
| `url` | where they were fetched from (a source can have several) |
| `data` | the bytes, as stored in the source (still compressed) |
| `hash` | a hash of `data` |
| `validator`, `checked_by` | the source's ETag, or its size and modification time for a local file, and which of the two was used |
| `fetched` | when |

A row is used only while its validator matches the source's current one,
so a source that changes is fetched again rather than served stale. Rows
are keyed on the source as a byte-reference table names it, before any
path remap, so a file read from a mirror and from its publisher shares
one set of rows.

The directory is append-only: each run writes new Parquet files, under a
partition per source (`ab/cd/<rest of the source's hash>/`), and never
rewrites old ones, so runs at the same time do not contend. Deleting the
directory empties the cache.

## Where it works

- `wxy warp` with a GeoTIFF or COG source, local or `https://`.
- `wxy warp` with a byte-reference table as the source: the cache sits
  inside the table reader, so every chunk read through a table is held
  (see [Byte-reference tables](../../explainers/byte-tables.md)).
- `--dry-run --cache DIR` adds held and missing counts and bytes to the
  plan.

## Where it stops

- `wxy points` and `wxy zonal` do not take `--cache` yet.
- Native Zarr stores are not cached; a Zarr store reached through a byte
  table is.
- Nothing is evicted. The cache grows until it is deleted.
- Held rows cannot yet be published as a store of their own (kerchunk
  with inline bytes, or Icechunk native chunks), though they already have
  the shape of one.
