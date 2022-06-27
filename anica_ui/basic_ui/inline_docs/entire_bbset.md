# Detailed Basic Block Set Exploration View

This page displays the entire set of basic blocks in a registered basic block set with the corresponding throughput measurements.
Its purpose is only to give a rough overview of what the basic block set looks like, advanced search methods are not supported as of now.
Each row of the table corresponds to one basic block of the set.


### Table Columns
Sorting the table is only possible by the value of the Basic Block (HEX) column.
Click the column title to do so, and click it again to reverse the order.

#### Basic Block (HEX)
This is the assembled encoding of the basic block, where each byte is represented by two hex digits.

#### Basic Block (ASM)
This is the disassembled basic block (in Intel assembly style, i.e., destination operand before source operands).

#### Predictor Results
These are the registered throughput measurements for the basic block.
For each identifier of a tool configuration, the corresponding value is listed.
The values are by convention the inverse throughput of the basic block, i.e., the average number of cycles required to execute the entire basic block in a steady state.

