# Single Campaign View

This view shows the details of a single discovery campaign:

### Tools under Investigation
Discovery campaigns search for interesting inconsistencies in the results of a number of throughput predictor tools (usually two).
The tools listed here were investigated for this campaign.

### Termination Condition
Discovery campaigns can be configured to terminate based on a variety of conditions:

  - time passed (`days`, `hours`, `minutes`, `seconds`): The campaign terminates if the specified time interval has passed.
  - `same_num_discoveries`: The campaign terminates if for the given number of batches, no new discoveries have been found.
  - `num_batches`: The campaign terminates if the specified number of batches has been investigated.
  - `num_discoveries`: The campaign terminates if the specified number of discoveries has been made.

The first time one of the conditions is satisfied after processing a batch, the campaign terminates.

### Abstraction Config

This is the detailed configuration used in the campaign for abstracting instructions, restricting instruction schemes, judging the interestingness of basic blocks and general parameters of the discovery algorithm.
Hover over the individual entries to see a short documentation of their meaning.

### Prefix Control

This section allows to select that only a prefix of the series of batches in the discovery campaign is considered for the following results and plots.
This is helpful to compare campaigns with widely different running times in a fair way, by comparing the results for the same number of batches.

### Result Summary

This section shows a number of metrics for the discovery campaign:

  - batches run: Discovery campaigns consist of a number of batches with a fixed number of sampled basic blocks that are investigated one after the other.
    This is the number of batches that were investigated during the campaign.
  - discoveries made: The number of discoveries, i.e. non-subsuming interesting abstract basic blocks, made during the discovery campaign.
  - discoveries per batch: The average (arithmetic mean) number of discoveries per batch.
  - average generality: The average over the minimal numbers of instruction schemes represented by any abstract instruction of the abstract blocks (i.e. `avg({min({len(absinsn.representedSchemes) for absinsn in discovery}) for discovery in Campaign})`).
  - average witness length: The average length of witnesses over all discoveries of the campaign.
  - average number of instructions: The average number of abstract instructions over all discoveries of the campaign.
  - time spent: The time that passed while performing the campaign.

### Plots

For a more detailed overview, this section displays plots concerning the entire campaign:

  - Discoveries per Batch: This graph shows the number of discoveries (vertical axis) for each batch in the campaign (horizontal axis).
  The batches are indexed by the order in which they are investigated in the campaign.
  - Generality of Discoveries: This is a histrogram showing the distribution of generality values in the discoveries of this campaign.

By default, the axis scales of plots for different campaigns may differ, which makes a comparison difficult.
To do comparisons between campaigns, there are controls below the plots that allow to specify a campaign with which the current campaign view should be made comparable with.

If a comparison campaign Y is set on the single campaign view for a campaign X and on a single campaign view for campaign Y, campaign X is set for comparison, the scales of the plots will be the same on both views.
If a batch prefix is specified, it should be specified in both views explicitly so that the scales are adjusted accordingly.

### Detailed Results:
  - All Discoveries: This is a link to a list of all discoveries made in this campaign.
  - All occurring Instruction Schemes: This is a link to a list of all instruction schemes that occur in any discovery of this campaign.

