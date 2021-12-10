# Single Discovery View

This shows the details of a single discovery:


### Discovery
These are representations of the abstract basic block constituting this discovery.

Abstract basic blocks contain two top-level components: abstract instructions and constraints on the aliasing of instruction operands.
Each abstract instruction contains subcomponents for abstract features.
These together form constraints on the set of instruction schemes that are represented by this abstract instruction.
At the end of each abstract instruction, this view contains a count of represented schemes with a `show` button that will display an explicit list of all instruction schemes represented by this abstract instruction when clicked (click again to hide).

The left, *original* abstract block is the direct result of the generalization algorithm.
The right, *narrowed* one is equivalent to the left one (i.e. its abstract instructions represent the same sets of instruction schemes), but the abstract instructions have been made as specific as possible.
This narrowing may ease interpreting the abstract block for humans.

### Remarks
This section displays more or less notable occurrences in the generalization of this discovery.

A more relevant example would be sampling errors, which would show up as non-zero sample fail ratios.
If the sample fail ratio is less than 0.5, enough basic block samples to satisfy the abstraction configuration could be found.
If it is greater, fewer samples are used (up to 1.0, in which case all samples failed.)

### Metrics

This section contains metrics for the discovery:

  - geomean interestingness: The geometric mean of the interestingnesses of a group of blocks sampled from the represented concrete basic blocks of this abstract block.
    The higher this value, the more dramatic is the deviation between the tools under investigation (may be infinite if at least one of the tools crashes).
  - sample coverage: The (approximated) ratio of samples from the universe of basic blocks (with the same number of instructions as this abstract block) that are represented by this discovery.
    The higher this ratio, the more general is this abstract block.
  - generality: The minimum number of instruction schemes represented by an abstract instruction of the abstract block.
    The larger this is, the more basic blocks are characterized as interesting by this discovery.
  - witness length: The length of the witness for the generalization of this discovery.
    The larger this is, the more generalization steps were used for this discovery.

### Plots

For a more detailed overview, this section displays plots concerning the properties of this discovery:

  - Interestingness of Samples: This is a histogram showing the distribution of interestingness values in the samples that justify this discovery.
    Infinite values are currently represented as values larger than any other occuring values, which is not really a good indicator.

(If plots are not present, the necessary data has not been computed before importing the discovery campaign.)

### Witness
This link leads to a site detailing how this discovery has been generalized from a concrete basic block.

