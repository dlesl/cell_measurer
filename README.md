This is a pair of scripts for measuring bacterial cell width and
length from phase contrast images, which should work for curved and
filamentous cells. It is semi-automated and allows for manual
inspection and correction/rejection of incorrect results. There are
two parts:

### An ImageJ macro (`Measure.java`)

This requires [Fiji](https://fiji.sc/).

The easiest way to run it is by dragging `Measure.java` onto the main
Fiji window and pressing 'Run'. Select a folder containing input files
(`.tif` format). Any images for which output files already exist will
be skipped. Cells are identified using 'Threshold', and 'Analyze
Particles'. You may need to adjust the parameters in the macro for
this to work well. After this stage, the macro pauses to allow you to
correct or remove any cells that were incorrectly detected.

Cells are then skeletonised to measure their length, and the distance
of the cell's outline from this skeleton is calculated using the
[Geodesic Distance Map](https://imagej.net/MorphoLibJ) plugin.

<img title="Example phase contrast image" src="examples/phase.png" width="200">
<img title="Example skeleton" src="examples/skel.png" width="200">
<img title="Example distance map" src="examples/dist.png" width="200">

### A Python script (`process.py`)

This requires Python 3.

This script processes the files created by the ImageJ macro. To the
final cell length, it extends the skeleton to the ends of the cell.

<img title="Example of skeleton extension" src="examples/skel_extension.png" width="400">

To find the mean cell width, excluding the end caps, it removes all
pixels within a defined radius from the ends of the skeleton. You can
customise this by changing `MASK_RADIUS`. This gives us just the
outline of the mid part of the cell.

<img title="Example of cell width" src="examples/masked_endcaps.png" width="400">

Since the pixel values are equal to their distance from the skeleton,
we can take their mean and multiply it by 2 to get the mean width of
the middle part of the cell.

The script provides a simple interface to allow you to vet the final
results in your web browser. You can press 'y' or 'n' to determine
which values make it to the final results table.
