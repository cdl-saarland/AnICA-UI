# Single Campaign View

This view shows the details of a single discovery campaign:

### Tools under Investigation
Discovery campaigns search for interesting deviations in the results of a number of throughput predictor tools (usually two).
The tools listed here were investigated for this campaign.

### Termination Condition
Discovery campaigns can be configured to terminate based on a variety of conditions:

  - time passed (`days`, `hours`, `minutes`, `seconds`): The campaign terminates if the specified time interval has passed.
  - `same_num_discoveries`: The campaign terminates if for the given number of batches, no new discoveries have been found.
  - `num_batches`: The campaign terminates if the specified number of batches has been investigated.
  - `num_discoveries`: The campaign terminates if the specified number of discoveries has been made.

The first time one of the conditions is satisfied after processing a batch, the campaign terminates.

### Abstraction Config

This is the detailed configuration used in the campaign for abstracting instructions, restricting instruction forms, judging the interestingness of basic blocks and general parameters of the discovery algorithm.
Hover over the individual entries to see a short documentation of their meaning.

### Result Summary

This section shows a number of metrics for the discovery campaign:

  - batches run: Discovery campaigns consist of a number of batches with a fixed number of sampled basic blocks that are investigated one after the other.
    This is the number of batches that were investigated during the campaign.
  - discoveries made: The number of discoveries, i.e. non-subsuming interesting abstract basic blocks, made during the discovery campaign.
  - discoveries per batch: The average (arithmetic mean) number of discoveries per batch.
  - avg witness length: The average length of witnesses over all discoveries of the campaign.
  - avg number of instructions: The average number of abstract instructions over all discoveries of the campaign.
  - time spent: The time that passed while performing the campaign.

### Plots

For a more detailed overview, this section displays plots concerning the entire campaign:

  - Discoveries per Batch: This graph shows the number of discoveries (vertical axis) for each batch in the campaign (horizontal axis).
  The batches are indexed by the order in which they are investigated in the campaign.


### Detailed Results:
  - All Discoveries: This is a link to a list of all discoveries made in this campaign.

