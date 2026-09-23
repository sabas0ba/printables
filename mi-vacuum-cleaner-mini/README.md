# Mi Vacuum Cleaner Mini holder

A horizontal cradle for Mi Vacuum Cleaner Mini (SSXCQ01XY). The two ends of
the semicircular cradle rise gradually to resist sliding along the body. The
front remains open for an attached nozzle, and the rear remains open for the
USB-C charging cable. Rounded side cutouts at the middle provide a handhold.

- [`holder.stl`](holder.stl): one printable part, 281 × 68 × 45 mm.
- [`generate.py`](generate.py): parametric CadQuery source, dimensions in mm.

Print with the flat underside on the bed. Check that the model fits the build
area before slicing. The end openings are 50 mm at the nozzle side and 36 mm
at the USB-C side before edge rounding. The design uses the manufacturer's
nominal body dimensions of 267 × 55 × 55 mm; the nozzle and plug clearances
and actual fit have not been verified on a physical unit.

The STL was generated with Python 3.12 and CadQuery 2.7.0. Run `generate.py`
in an environment containing that CadQuery version to regenerate `holder.stl`.
After changing the geometry, inspect the result and verify that it is a valid,
single closed solid before printing.

License: [CC BY-SA 4.0](../LICENSE.md). This is an independent accessory and
is not an official Xiaomi product.
