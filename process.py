#!/usr/bin/python3
from glob import glob
from os import path
from sys import argv
import sys
from mahotas import bwperim
import numpy as np
import numpy.polynomial.polynomial as poly
from numpy.linalg import norm
import matplotlib.pyplot as plt
from skimage import draw
from io import BytesIO
import base64

MIN_AREA = 20
MASK_RADIUS = 7  # radius to remove around end caps
END_RADIUS = 5  # radius for calculating the location of the ends
MIN_PIXELS = 5  # minimum number of pixels for width calculation


def load(basename):
    fname = basename + ".csv"
    lines = [l.strip().split(",") for l in open(fname)]
    lines = lines[1:]
    if len(lines) < MIN_AREA:
        return None
    sfname = basename + "-skel.csv"
    slines = [l.strip().split(",") for l in open(sfname)]
    slines = slines[1:]
    xs = [int(l[0]) for l in lines]
    ys = [int(l[1]) for l in lines]
    vs = [float(l[2]) for l in lines]

    # load skeleton
    sxs = [int(l[0]) for l in slines]
    sys = [int(l[1]) for l in slines]
    svs = [0 if int(l[2]) == 0 else 1 for l in slines]
    assert np.array_equal(xs, sxs)
    assert np.array_equal(ys, sys)

    min_x = min(xs) - 1
    min_y = min(ys) - 1
    im = np.zeros((max(xs) - min_x + 2, max(ys) - min_y + 2))
    mask = np.zeros(im.shape)
    skel = np.zeros(im.shape)
    for (x, y, v, sv) in zip(xs, ys, vs, svs):
        im[x - min_x, y - min_y] = v
        mask[x - min_x, y - min_y] = 1
        skel[x - min_x, y - min_y] = sv
    (h, w) = im.shape
    if w > h:
        return (mask, im, skel)
    else:
        return (np.transpose(mask), np.transpose(im), np.transpose(skel))


def run(basename):
    ims = load(basename)
    if ims is not None:
        print(basename)
        (mask, im, skel) = ims
        perim = bwperim(mask)
        im[perim == 0] = 0
        # plt.figure()
        # plt.imshow(im)
        # plt.savefig(basename + ".png")
        # plt.show()
        # plt.close()
        (h, w) = im.shape
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
        plt.imshow(im + skel)

        if len(ends) != 2:
            print("Something went wrong, only one end found!!!")
            plt.figure()
            plt.imshow(skel)
            plt.savefig(basename + "broken_end_detection.png")
            print(basename + "broken_end_detection.png")
            return None
        # Just the ends, to find tangent lines

        extra_len = 0

        for (i, j) in ends:
            end_mask = np.zeros(im.shape)
            (rr, cc) = draw.circle(i, j, END_RADIUS, im.shape)
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
        # plt.show()
        plt.close()

        # blank out an area around the ends
        for (i, j) in ends:
            (rr, cc) = draw.circle(i, j, MASK_RADIUS, im.shape)
            im[rr, cc] = 0

        plt.figure()
        plt.imshow(im)
        # plt.show()
        plt.savefig(basename + "-masked.png")
        plt.close()
        pixels = im[im != 0]
        if len(pixels) < MIN_PIXELS:
            print("Couldn't calculate width - too few pixels: {}".format(len(pixels)))
        else:
            mean_width = np.mean(pixels)
            # load skeleton length
            fname = basename + "-skel_info.csv"
            lines = [l.strip().split(",") for l in open(fname)]
            skel_length = float(lines[1][8])
            branches = int(lines[1][0])
            return (skel_file, mean_width, skel_length, extra_len, branches)
        return None


def do_dir(d):
    print(d)
    dirname = d
    if dirname[-1] == "/":
        dirname = dirname[:-1]
    with open(dirname + "-res.tsv", "w") as out:
        print("mean_width\tskel_length", file=out)
        for f in glob(path.join(d, "*.csv")):
            print(f)
            if not "skel" in f:
                try:
                    res = run(f.replace(".csv", ""))
                except:
                    print(sys.exc_info()[0])
                if res is not None:
                    (im, w, l, extra, branches) = res
                    resp = yield (im, l + extra, branches)
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
    gen = do_dir(dir)
    return do("start")


@app.route("/do/<cmd>")
def do_route(cmd):
    return do(cmd)

def do(cmd):
    global gen
    global threshold, accept_all
    try:
        im, l, branches = gen.send(None if cmd == "start" else cmd == "yes")
    except StopIteration:
        return '<h1>Done</h1><p><a href="/">New analysis</a></p>'
    im = base64.encodestring(im.getvalue()).decode("utf8")
    if accept_all:
        if branches == 1 and (threshold == 0 or l > threshold):
            aa = "y"
        else:
            aa = "n"
        script = '<script>window.addEventListener("load", () => document.getElementById("{}").click());</script>'.format(
            aa
        )
    else:
        script = "<script>window.addEventListener('keydown', e => document.getElementById(e.key).click())</script>"
    return """<h2>{} branches</h2>
              <img src="data:image/png;base64,{}" />
              <br/>Len: {}<br/>
              <a id="y" href="/do/yes">Yes</a><br/>
              <a id="n" href="/do/no">No</a>
              {}""".format(
        branches, im, l, script
    )

if __name__ == "__main__":
    app.run()
