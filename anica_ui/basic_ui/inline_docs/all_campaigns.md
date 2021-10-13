# All Campaigns View

This view gives an overview over all discovery campaigns currently registered.

### Table Columns
Sorting the table by the value of a specific column is possible for most columns.
Click the column title to do so, and click it again to reverse the order.

#### Campaign ID
This is the unique identifier for the discovery campaign, determined by the order in which the discovery campaigns were imported.
They link to a view with more details and results for the discovery campaign.

#### Start Date
The date when the discovery campaign was started.

#### Tools under Investigation
Discovery campaigns search for interesting deviations in the results of a number of throughput predictor tools (usually two).
This column lists which tools where used for this discovery campaign.

#### Config Delta

This column shows the relevant differences of the configuration used for the discovery campaign from a common base of the configurations of all registered campaigns.
Entries prefixed with a `+` are added, those with a `-` are discarded compared to the common base.
A dashed entry means that the configuration is identical to the common base configuration.
The full configuration with a documentation of the meaning of the options can be found on the single campaign view.

#### # Batches
Discovery campaigns consist of a number of batches with a fixed number of sampled basic blocks that are investigated one after the other.
This column gives the number of batches that were investigated during the campaign.

#### # Discoveries
This column shows the number of discoveries, i.e. non-subsuming interesting abstract basic blocks, made during the discovery campaign.

#### IISR
This is the **Initial Interesting Sample Ratio**, that is the number of interesting samples in the first batch divided by the number of sampled basic blocks per batch in the first batch.
The closer this metric is to 1.0, the more likely it is to find an interesting basic block through random sampling.

#### Run-Time
The time that passed while performing the discovery campaign.


### Comparisons

This is a convenience tool to open browser windows for multiple campaigns with plots scaled and prefixes aligned such that they are more easily comparable.
Just enter the Campaign IDs of all desired campaigns, separated by spaces, and click the button or press enter to confirm.

<b>Warning:</b> Your browser's pop-up blocker might forbid opening windows for all campaigns at once. You might want to check if pop-ups have been blocked if windows are missing.

