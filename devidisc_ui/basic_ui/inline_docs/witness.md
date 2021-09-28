# Witness View

This page shows the decisions taken in the generalization of a specific discovery and why they were taken.

The decisions are arranged in a tree with abstract basic blocks as nodes.
The root (on the top, blue) is the starting abstract block, which was directly abstracted from a concrete basic block.

Successors have one component (highlighted in orange) changed compared to their predecessor.
If this change still produced an *interesting* result, the corresponding abstract block is taken (green) and used to continue generalization.
If the change made a not uniformly interesting result, it is discarded (red).
If no more fresh choices for generalization are available, the procedure terminates.

You can click on abstract blocks to display a list of sampled concrete basic blocks that were used to judge its interestingness.

