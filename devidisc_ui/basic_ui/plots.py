"""
A helper module containing several functions for creating matplotlib plots for
display in views.

The plots are rendered as png files, which are then base64-encoded and directly
inserted into the html templates.

The idea for this comes from this page:
    https://spapas.github.io/2021/02/08/django-matplotlib/
"""

import math

import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import io, base64


def encode_plot(fig):
    flike = io.BytesIO()
    fig.savefig(flike)
    b64 = base64.b64encode(flike.getvalue()).decode()
    return b64


def make_discoveries_per_batch_plot(batches, cmp_batches=[]):
    objs = batches

    xlimit = len(objs)

    batch_idx = list(range(0, xlimit))
    counts = [x.discovery_set.count() for x in objs]

    ylimit = max(counts)

    for inner_cmp_batches in cmp_batches:
        max_cmp_count = max((x.discovery_set.count() for x in inner_cmp_batches))
        ylimit = max(ylimit, max_cmp_count)
        xlimit = max(xlimit, len(inner_cmp_batches))

    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(batch_idx, counts, '--bo')

    ax.set_title('Discoveries per Batch')
    ax.set_ylabel("# Discoveries")
    ax.set_xlabel("Batch Index")

    xmargin = max(xlimit * 0.05, 5)
    ymargin = max(ylimit * 0.05, 1)
    ax.set_xlim(-xmargin, xlimit + xmargin)
    ax.set_ylim(-ymargin, ylimit + ymargin)

    ax.grid(linestyle="--", linewidth=0.5, color='.25', zorder=-10)

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    return encode_plot(fig)

def make_generality_histogramm_plot(discoveries, cmp_discoveries=[]):
    num_bins = 16

    entries = [ d.generality for d in discoveries ]

    xlimit = max(entries)
    ylimit = len(entries)

    for inner_cmp_discoveries in cmp_discoveries:
        cmp_entries = [ d.generality for d in inner_cmp_discoveries ]
        xlimit = max(xlimit, max(cmp_entries))
        ylimit = max(ylimit, len(cmp_entries))

    xmargin = xlimit * 0.05
    ymargin = ylimit * 0.05

    fig, ax = plt.subplots(figsize=(10,6))
    counts, bins, patches = ax.hist(entries, bins=num_bins, range=(0, xlimit))

    ax.set_title('Generality of Discoveries')
    ax.set_ylabel("# Occurrences")
    ax.set_xlabel("Generality")

    ax.set_xlim(-xmargin, xlimit + xmargin)
    ax.set_ylim(-ymargin, ylimit + ymargin)

    ax.grid(linestyle="--", linewidth=0.5, color='.25', zorder=-10)

    ax.set_xticks(bins)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    # Label the raw counts below the x-axis...
    # ajusted from https://stackoverflow.com/a/6353051
    bin_centers = 0.5 * np.diff(bins) + bins[:-1]
    for count, x in zip(counts, bin_centers):
        # Label the raw counts
        ax.annotate("{:.0f}".format(count), xy=(x, 0), xycoords=('data', 'axes fraction'),
            xytext=(0, -18), textcoords='offset points', va='top', ha='center')

    fig.subplots_adjust(bottom=0.15)
    ax.xaxis.labelpad = 26

    return encode_plot(fig)

def make_interestingness_histogramm_plot(measurements):
    interestingnesses = [ m.interestingness for m in measurements ]

    finite_entries = [i for i in interestingnesses if math.isfinite(i)]
    if len(finite_entries) == 0:
        return None
    max_finite = max(finite_entries)
    inf_val = abs(max_finite) * 1.5

    entries = [i if math.isfinite(i) else inf_val for i in interestingnesses]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.hist(entries)

    ax.set_title('Interestingness of Samples')
    ax.set_ylabel("# Occurrences")
    ax.set_xlabel("Interestingness")
    ax.grid(linestyle="--", linewidth=0.5, color='.25', zorder=-10)

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    return encode_plot(fig)


