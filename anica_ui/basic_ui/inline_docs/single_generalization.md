# Single Generalization View

This shows the details of a single specific generalization and its resulting discovery:


### Discovery
These are representations of the abstract basic block constituting this discovery.

Abstract basic blocks contain two top-level components: abstract instructions and constraints on the aliasing of instruction operands.
Each abstract instruction contains subcomponents for abstract features.
These together form constraints on the set of instruction schemes that are represented by this abstract instruction.
At the end of each abstract instruction, this view contains a count of represented schemes with a `show` button that will display an explicit list of all instruction schemes represented by this abstract instruction when clicked (click again to hide).

The left, *original* abstract block is the direct result of the generalization algorithm.
The right, *narrowed* one is equivalent to the left one (i.e. its abstract instructions represent the same sets of instruction schemes), but the abstract instructions have been made as specific as possible.
This narrowing may ease interpreting the abstract block for humans.

### Example Results
Here, a small number of basic blocks that were sampled from the discovery with the corresponding predictions are shown.
They are selected somewhat evenly wrt. interestingness from all sampled basic blocks.

For more results, view the corresponding witness page and click on the relevant abstract block of interest to open its measurement site in a side view.

### Remarks
This section displays more or less notable occurrences in the generalization of this discovery.

A more relevant example would be sampling errors, which would show up as non-zero sample fail ratios.
If the sample fail ratio is less than 0.5, enough basic block samples to satisfy the abstraction configuration could be found.
If it is greater, fewer samples are used (up to 1.0, in which case all samples failed.)

### Metrics

This section contains metrics for the discovery:

  - generality: The minimum number of instruction schemes represented by an abstract instruction of the abstract block.
    The larger this is, the more basic blocks are characterized as interesting by this discovery.
  - witness length: The length of the witness for the generalization of this discovery.
    The larger this is, the more generalization steps were used for this discovery.


### Witness
This link leads to a site detailing how this discovery has been generalized from a concrete basic block.


### Abstraction Config

This is the detailed configuration used in the generalization for abstracting instructions, restricting instruction forms, judging the interestingness of basic blocks.
Hover over the individual entries to see a short documentation of their meaning.


