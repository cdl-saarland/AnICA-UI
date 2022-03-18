# All Generalizations View

This view gives an overview over all generalizations currently registered.

### Table Columns
Sorting the table by the value of a specific column is possible for most columns.
Click the column title to do so, and click it again to reverse the order.

#### Generalization ID
This is the unique identifier for the generalization, determined by the order in which the generalizations were imported.
They link to a view with more details and results for the generalization.

#### Tools under Investigation
Generalizations search for interesting deviations in the results of a number of throughput predictor tools (usually two).
This column lists which tools where used for this generalization.

#### Abstract Block
An abridged representation of the abstract basic block that constitutes this generalization result, where all TOP entries are omitted.

Abstract basic blocks contain two top-level components: abstract instructions and constraints on the aliasing of instruction operands.
Each abstract instruction contains subcomponents for abstract features. The number in parentheses behind each abstract instruction is the number of concrete instruction schemes that are represented by this abstract instruction.

The linked page with details for the generalization contains the unabridged representation with a full list of the represented instruction schemes.

#### Mean Interestingness
The geometric mean of the interestingnesses of a group of blocks sampled from the represented concrete basic blocks of this abstract block.
The higher this value, the more dramatic is the deviation between the tools under investigation (may be infinite if at least one of the tools crashes).

#### Generality
The minimum number of instruction schemes represented by an abstract instruction of the abstract block.
The larger this is, the more basic blocks are characterized as interesting by this generalization result.

#### Witness Length
The length of the witness for the generalization.
The larger this is, the more generalization steps were used.

