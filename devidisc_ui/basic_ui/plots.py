"""
A helper module containing several functions for creating matplotlib plots for
display in views.

The plots are rendered as png files, which are then base64-encoded and directly
inserted into the html templates.

The idea for this comes from this page:
    https://spapas.github.io/2021/02/08/django-matplotlib/
"""

import math

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


def make_discoveries_per_batch_plot(batches):
    objs = batches

    batch_idx = list(range(0, len(objs)))
    counts = [x.discovery_set.count() for x in objs]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(batch_idx, counts, '--bo')

    ax.set_title('Discoveries per Batch')
    ax.set_ylabel("# Discoveries")
    ax.set_xlabel("Batch Index")
    ax.grid(linestyle="--", linewidth=0.5, color='.25', zorder=-10)

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

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


def make_generality_histogramm_plot(discoveries):
    entries = [ d.generality for d in discoveries ]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.hist(entries)

    ax.set_title('Generality of Discoveries')
    ax.set_ylabel("# Occurrences")
    ax.set_xlabel("Generality")
    ax.grid(linestyle="--", linewidth=0.5, color='.25', zorder=-10)

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    return encode_plot(fig)
