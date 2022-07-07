# Single Basic Block Set View

This view shows with a heatmap how many basic blocks in the selected basic block set cause inconsistencies for certain predictor pairs and the computed discovery campaign coverage metrics.

## Interestingness Heatmap

Each square shows the percentage of entries in the basic block set where a pair of throughput predictors disagree with a relative difference of more than 50%.


## Campaign Coverage Results
Each row corresponds to one discovery campaign that has been imported to the UI and whose metrics have been computed via command line.
After importing a discovery campaign, you will need to use the `./manage.py compute_bbset_coverage --campaigns X [--bbsets Y]` command with the corresponding campaign ID (and basic block set) to compute these metrics and to see them here.

### Table Columns
Sorting the table by the value of a specific column is possible for most columns.
Click the column title to do so, and click it again to reverse the order.

#### Campaign
The ID of the discovery campaign that contributed this table row.
Click it to get to the discovery campaign.

#### Campaign Tag
The tag of the discovery campaign, as specified when importing it.
Click a value to get to a view only showing campaigns with this tag.

#### Tools under Investigation
Discovery campaigns search for interesting deviations in the results of a number of throughput predictor tools (usually two).
This column lists which tools where used for this discovery campaign.

#### # Discoveries
This column shows the number of discoveries, i.e. non-subsuming interesting abstract basic blocks, made during the discovery campaign.

#### Run-Time
The time that passed while performing the discovery campaign.

#### # BBs interesting
The number (and percentage) of basic blocks from the basic block set that are interesting by the interestingness metric and the tools under investigation of the discovery campaign.

#### int. BBs covered
The percentage of interesting basic blocks (that were counted for the previous column) that are covered by some abstract basic block in the discovery campaign.
In parentheses is the corresponding total number of such basic blocks.

#### int. BBs covered by top 10
The percentage of interesting basic blocks that are covered by the 10 most general abstract basic blocks in the discovery campaign.
In parentheses is the corresponding total number of such basic blocks.

