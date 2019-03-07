package cell_measurer;

import ij.IJ;
import ij.ImagePlus;
import ij.Prefs;
import ij.WindowManager;
import ij.gui.Roi;
import ij.plugin.PlugIn;
import ij.plugin.frame.RoiManager;
import ij.process.ImageProcessor;
import ij.gui.WaitForUserDialog;
import java.io.File;

import java.util.Arrays;
import java.util.Hashtable;
import java.util.stream.IntStream;

import ij.gui.GenericDialog;
import ij.gui.ImageWindow;
import ij.io.Opener;
import ij.WindowManager;

public class Measure implements PlugIn {
	public void closeAll() {
		int[] l = WindowManager.getIDList();
		if (l != null) {
			for (final int id : l) {
				final ImagePlus imp = WindowManager.getImage(id);
				if (imp == null)
					continue;
				imp.changes = false;
				imp.close();
			}
		}
		System.gc();
	}

	public void run(String s) {
		String dir = IJ.getDirectory("Files?");
		String out = IJ.getDirectory("Where to save?");
		File[] files = new File(dir).listFiles((_dir, name) -> name.toLowerCase().endsWith(".tif"));
		for (File f : files) {
			closeAll();
			String outTest = out + "DUP_" + f.getName().replace(".tif", "-0.txt");
			if (!new File(outTest).exists())
				if (!actuallyRun(f.getAbsolutePath(), out)) {
					return;
				}
		}
	}

	boolean actuallyRun(String f, String out) {
		ImagePlus im = new Opener().openImage(f);

		// necessary to ensure we get measurements in pixels
		IJ.run(im, "Set Scale...", "distance=0 known=0");
		RoiManager rois = RoiManager.getRoiManager();
		if (rois.getCount() > 0) {
			int[] indices = IntStream.range(0, rois.getCount()).toArray();
			rois.setSelectedIndexes(indices);
			rois.runCommand("Delete");
		}
		im.show();
		im = im.duplicate();
		im.show();
		IJ.setAutoThreshold(im, "Intermodes");
		// IJ.setAutoThreshold(im, "Default");
		Prefs.blackBackground = false;
		IJ.run(im, "Convert to Mask", null);
		IJ.run(im, "Analyze Particles...", "size=200-20000 pixel exclude clear add");
		IJ.run("Tile");
		GenericDialog d = new GenericDialog("Controls");
		d.addMessage("Choose an option from the menu");
		d.addChoice("", new String[] { "continue", "skip" }, "continue");
		d.showDialog();
		if (d.wasCanceled())
			return false;
		if (d.getNextChoice() == "skip" || rois.getCount() == 0) {
			return true;
		}
		new WaitForUserDialog("Fix the ROIs, then press OK!\nDon't press it yet (I know it's as reflex :) )").show();
		int[] indices = IntStream.range(0, rois.getCount()).toArray();
		rois.setSelectedIndexes(indices);
		rois.runCommand(im, "Combine");
		IJ.setBackgroundColor(255, 255, 255);
		IJ.run(im, "Clear Outside", "");
		IJ.run(im, "Select All", "");
		rois.deselect();
		for (int roi : rois.getIndexes()) {
			rois.deselect();
			rois.select(im, roi);
			IJ.run(im, "Save XY Coordinates...", "save=[" + out + im.getTitle() + "-" + roi + ".txt]");
		}
		return true;
	}
}
