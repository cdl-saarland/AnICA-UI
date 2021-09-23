# All Discoveries View

This view gives an overview over all discoveries of a single discovery campaign.


### Table Columns
Sorting the table by the value of a specific column is possible for most columns.
Click the column title to do so, and click it again to reverse the order.

#### Discovery ID
This is the unique (per campaign) identifier for the discovery, determined by the order in which the discoveries were made.
Discovery identifiers consist of three parts: the index of the batch to which it belongs, the index of the sampled basic block in the batch from which it was generalized, and the index of the generalization attempt for this basic block.
They link to a view with more details.

#### Abstract Block
An abridged representation of the abstract basic block that constitutes this discovery, where all TOP entries are omitted.

Abstract basic blocks contain two top-level components: abstract instructions and constraints on the aliasing of instruction operands.
Each abstract instruction contains subcomponents for abstract features. The number in parentheses behind each abstract instruction is the number of concrete instruction schemes that are represented by this abstract instruction.

The linked page with details for the discovery contains the unabridged representation with a full list of the represented instruction schemes.

#### # Instructions
The number of abstract instructions in the abstract block.

#### Sample Coverage
The (approximated) ratio of samples from the universe of basic blocks (with the same number of instructions as this abstract block) that are represented by this discovery.
The higher this ratio, the more general is this abstract block.

#### Mean Interestingness
The geometric mean of the interestingnesses of a group of blocks sampled from the represented concrete basic blocks of this abstract block.
The higher this value, the more dramatic is the deviation between the tools under investigation (may be infinite if at least one of the tools crashes).

#### Generality
The minimum number of instruction schemes represented by an abstract instruction of the abstract block.
The larger this is, the more basic blocks are characterized as interesting by this discovery.

#### Witness Length
The length of the witness for the generalization of this discovery.
The larger this is, the more generalization steps were used for this discovery.

