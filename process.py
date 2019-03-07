#!/usr/bin/python3
from glob import glob
from os import path
from sys import argv
import sys
from mahotas import bwperim, distance
import numpy as np
import numpy.polynomial.polynomial as poly
from numpy.linalg import norm
import matplotlib.pyplot as plt
from skimage import draw
from io import BytesIO
import base64
from skimage.morphology import skeletonize
from skan import csr

MIN_AREA = 20
MASK_RADIUS = 7  # radius to remove around end caps
END_RADIUS = 5  # radius for calculating the location of the ends
MIN_PIXELS = 5  # minimum number of pixels for width calculation


def load(basename):
    fname = basename + ".txt"
    lines = [l.strip().split("\t") for l in open(fname)]
    lines = lines[1:]
    if len(lines) < MIN_AREA:
        return None
    xs = [int(l[0]) for l in lines]
    ys = [int(l[1]) for l in lines]
    assert all((l[2] == '255' for l in lines))
    min_x = min(xs) - 1
    min_y = min(ys) - 1
    mask = np.zeros((max(xs) - min_x + 2, max(ys) - min_y + 2))
    for (x, y) in zip(xs, ys):
        mask[x - min_x, y - min_y] = 1
    skel = skeletonize(mask)
    dist = distance(np.invert(skel))
    # plt.figure()
    # plt.imshow(skel)
    # plt.savefig(basename + '_skeleton.png')
    # plt.close()
    lengths = csr.summarise(skel)
    if lengths.shape[0] is not 1:
        print("%d branches found, skipping `%s`" % (lengths.shape[0], basename))
        plt.figure()
        plt.imshow(skel)
        plt.savefig(basename + 'branched_skeleton.png')
        plt.close()
    skel_length = lengths['branch-distance'].values[0]
    skel = skel.astype(int)
    (h, w) = mask.shape
    if w > h:
        return (mask, dist, skel, skel_length)
    else:
        return (np.transpose(mask), np.transpose(dist), np.transpose(skel), skel_length)


def run(basename, mask_endcaps, use_median):
    ims = load(basename)
    if ims is not None:
        print(basename)
        (mask, dist, skel, skel_length) = ims
        perim = bwperim(mask)
        dist[perim == 0] = 0
        dist = np.sqrt(dist) # mahotas.distance returns squared distances
        plt.figure()
        plt.imshow(dist)
        plt.savefig(basename + ".png")
        plt.close()
        (h, w) = dist.shape
        # find the ends of the skeleton - pixels where only one neighbour == 1
        ends = []
        for j in range(w):
            for i in range(h):
                if skel[i, j] == 1:
                    nb = (
                        skel[i - 1, j - 1]
                        + skel[i - 1, j]
                        + skel[i - 1, j + 1]
                        + skel[i, j - 1]
                        + skel[i, j + 1]
                        + skel[i + 1, j - 1]
                        + skel[i + 1, j]
                        + skel[i + 1, j + 1]
                    )
                    if nb == 1:
                        ends.append((i, j))
        plt.figure()
        plt.imshow(dist + skel)

        if len(ends) != 2:
            print("Something went wrong, %d ends found!!!" % len(ends))
            plt.figure()
            plt.imshow(skel)
            plt.savefig(basename + "broken_end_detection.png")
            print(basename + "broken_end_detection.png")
            return None
        # Just the ends, to find tangent lines

        extra_len = 0

        for (i, j) in ends:
            end_mask = np.zeros(dist.shape)
            (rr, cc) = draw.circle(i, j, END_RADIUS, dist.shape)
            end_mask[rr, cc] = 1

            end_skel = np.copy(skel) * end_mask

            col, row = end_skel.nonzero()
            coefs = poly.polyfit(row, col, 1)
            ffit = poly.Polynomial(coefs)
            x_new = np.linspace(np.min(row), np.max(row), 1000)
            plt.plot(x_new, ffit(x_new))

            # find intersection with cell outline
            x = j
            jj = j
            # go left
            while mask[int(np.rint(ffit(j - 0.1))), int(np.rint(j - 0.1))] == 1:
                j = j - 0.1
            # go right
            while mask[int(np.rint(ffit(jj + 0.1))), int(np.rint(jj + 0.1))] == 1:
                jj = jj + 0.1

            i = ffit(j)
            y = ffit(x)  # cleaner
            # get distance
            l = norm(np.array((x, y)) - np.array((j, i)))

            ii = ffit(jj)
            ll = norm(np.array((x, y)) - np.array((jj, ii)))

            # was going right shorter?
            if ll < l:
                j = jj
                l = ll
                i = ii

            extra_len = extra_len + l
            plt.plot((j, x), (i, y), marker="o")

        skel_file = BytesIO()
        plt.savefig(skel_file)
        plt.close()

        if mask_endcaps:
            # blank out an area around the ends
            for (i, j) in ends:
                (rr, cc) = draw.circle(i, j, MASK_RADIUS, dist.shape)
                dist[rr, cc] = 0

        plt.figure()
        plt.imshow(dist)
        plt.savefig(basename + "-masked.png")
        plt.close()
        pixels = dist[dist != 0]
        if len(pixels) < MIN_PIXELS:
            print("Couldn't calculate width - too few pixels: {}".format(len(pixels)))
        else:
            if use_median:
                mean_width = np.median(pixels)
            else:
                mean_width = np.mean(pixels)
            return (skel_file, mean_width, skel_length, extra_len)
        return None


def do_dir(d, mask_endcaps, use_median):
    print(d)
    dirname = d
    if dirname[-1] == "/":
        dirname = dirname[:-1]
    with open(dirname + "-res.tsv", "w") as out:
        print("mean_width\tskel_length", file=out)
        for f in glob(path.join(d, "*.txt")):
            print(f)
            if not "skel" in f:
                try:
                    res = run(f.replace(".txt", ""), mask_endcaps, use_median)
                except:
                    print(sys.exc_info()[0])
                if res is not None:
                    (im, w, l, extra) = res
                    resp = yield (im, l + extra)
                    print(resp)
                    if resp:
                        print("{}\t{}".format(w, l + extra), file=out)


from flask import Flask, request
import os

app = Flask(__name__, static_folder=os.getcwd())


gen = None
threshold = None
accept_all = False


@app.route("/")
def index():
    return """
        <form action="/start" method="GET">
            <label>Dir: <input type="text" name="dir"/></label></br>
            <label>Skip when length below: <input type="number" name="threshold" value="0"/></label></br>
            <label>Auto accept all<input type="checkbox" name="accept_all"/></label></br>
            <label>Exclude endcaps<input type="checkbox" name="mask_endcaps" checked/></label></br>
            <label>Use median<input type="checkbox" name="use_median"/></label></br>
            <button>Start</button>
        </form>
    """

@app.route("/start")
def start():
    global gen
    global threshold, accept_all
    dir = request.args.get("dir")
    threshold = float(request.args.get("threshold"))
    accept_all = bool(request.args.get("accept_all"))
    mask_endcaps = bool(request.args.get("mask_endcaps"))
    use_median = bool(request.args.get("use_median"))
    gen = do_dir(dir, mask_endcaps, use_median)
    return do("start")


@app.route("/do/<cmd>")
def do_route(cmd):
    return do(cmd)

def do(cmd):
    global gen
    global threshold, accept_all
    try:
        im, l = gen.send(None if cmd == "start" else cmd == "yes")
    except StopIteration:
        return '<h1>Done</h1><p><a href="/">New analysis</a></p>'
    im = base64.encodebytes(im.getvalue()).decode("utf8")
    if accept_all:
        if threshold == 0 or l > threshold:
            aa = "y"
        else:
            aa = "n"
        script = '<script>window.addEventListener("load", () => document.getElementById("{}").click());</script>'.format(
            aa
        )
    else:
        script = "<script>window.addEventListener('keydown', e => document.getElementById(e.key).click())</script>"
    return """<img src="data:image/png;base64,{}" />
              <br/>Len: {}<br/>
              <a id="y" href="/do/yes">Yes</a><br/>
              <a id="n" href="/do/no">No</a>
              {}""".format(
        im, l, script
    )

if __name__ == "__main__":
    app.run()
