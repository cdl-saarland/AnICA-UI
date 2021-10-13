# All InsnSchemes View

This view gives an overview over all instruction schemes that occur in any discovery of a single discovery campaign.

An instruction scheme (InsnScheme) represents a group of instruction instances that differ only in the concrete values of their operand fields.
E.g. two instruction instances belonging to the same InsnScheme may have different register operands of the same width, or different immediate values of the same width, or different memory operands of the same width.
They may not have, e.g., different opcodes, register operands with different widths at the same operand position, or different operand types.

### Table Columns
Sorting the table by the value of a specific column is possible.
Click the column title to do so, and click it again to reverse the order.

#### InsnScheme
A textual representation of the InsnScheme.
Click it to see a site with more detailed information about it.

#### Total Occurrences
The total number of discoveries in this discovery campaign that have an abstract instruction that also represents this instruction scheme.

#### Numbered Columns
These columns show for each occurring length of abstract basic blocks the number of occurrences of the instruction scheme in a discovery with this number of instructions.
For each row, the sum of the values in these columns should be the same as the `TotalOccurrences` value.

If an InsnScheme has, e.g., a non-zero entry in the `L1` column, that means that there are discoveries concerning this InsnScheme in separation.


