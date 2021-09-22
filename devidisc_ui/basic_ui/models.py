from django.db import models
from django.utils.dateparse import parse_datetime

import json
from pathlib import Path

from devidisc.configurable import load_json_config

import logging
logger = logging.getLogger(__name__)


class Tool(models.Model):
    full_name = models.CharField(max_length=255)

    def __str__(self):
        return self.full_name

class Campaign(models.Model):
    config_dict = models.JSONField()
    tools = models.ManyToManyField(Tool)
    termination_condition = models.JSONField()

    date = models.DateField()
    host_pc = models.CharField(max_length=255)
    total_seconds = models.IntegerField()

    @property
    def display_name(self):
        return str(self)

    def __str__(self):
        return f"{self.host_pc} - {self.date}"

class DiscoveryBatch(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    batch_index = models.IntegerField()
    num_sampled = models.IntegerField()
    num_interesting = models.IntegerField()
    batch_time = models.IntegerField()

    class Meta:
        indexes = [
                models.Index(fields=('batch_index', 'campaign')),
            ]

class InsnScheme(models.Model):
    text = models.CharField(max_length=255)

    def __str__(self):
        return self.text

class Discovery(models.Model):
    batch = models.ForeignKey(DiscoveryBatch, on_delete=models.CASCADE)
    identifier = models.CharField(max_length=63)
    absblock = models.JSONField()
    num_insns = models.IntegerField()
    witness_len = models.IntegerField()
    interestingness = models.FloatField()
    ab_coverage = models.FloatField()
    occuring_insnschemes = models.ManyToManyField(InsnScheme)

    def __str__(self):
        return self.identifier

class Measurement(models.Model):
    discovery = models.ForeignKey(Discovery, on_delete=models.CASCADE)
    interestingness = models.FloatField()


class Witness(models.Model):
    discovery = models.OneToOneField(Discovery, on_delete=models.CASCADE)


def import_campaign(campaign_dir):
    base_dir = Path(campaign_dir)

    campaign_config = load_json_config(base_dir / "campaign_config.json")

    abstraction_config = campaign_config["abstraction_config"]
    tools = campaign_config['predictors']
    termination_condition = campaign_config['termination']

    report = load_json_config(base_dir / "report.json")

    date = parse_datetime(report['start_date'])
    total_seconds = report['seconds_passed']
    host_pc = report['host_pc']

    tool_objs = [Tool.objects.get_or_create(full_name=tool_name, defaults={})[0] for tool_name in tools]

    campaign = Campaign(
            config_dict = abstraction_config,
            termination_condition = termination_condition,
            date = date,
            host_pc = host_pc,
            total_seconds = total_seconds,
        )

    campaign.save()

    for t in tool_objs:
        campaign.tools.add(t.id)

    # check whether there is a file containing metrics produced in a preprocessing step
    metrics_path = base_dir / 'metrics.json'
    if metrics_path.exists():
        with open(metrics_path, 'r') as f:
            metrics_dict = json.load(f)
    else:
        metrics_dict = {}

    # Create all the batch and sample objects
    # Bulk creation is key here for reasonable performance!

    batch_objs = []
    for batch_index, batch_entry in enumerate(report['per_batch_stats']):
        num_sampled = batch_entry['num_sampled']
        num_interesting = batch_entry['num_interesting']
        batch_time = batch_entry['batch_time']
        batch_objs.append(DiscoveryBatch(
                campaign=campaign,
                batch_index=batch_index,
                num_sampled=num_sampled,
                num_interesting=num_interesting,
                batch_time=batch_time,
            ))
    DiscoveryBatch.objects.bulk_create(batch_objs)

    # We need to retrieve the bulk-inserted objects with an additional query,
    # since most db backends do not provide the ids of bulk-inserted objects.
    # Nevertheless, this is a lot faster than creating each batch object
    # individually.
    batch_objs = DiscoveryBatch.objects.filter(campaign=campaign)

    discovery_objs = []
    for batch_entry, batch_obj in zip(report['per_batch_stats'], batch_objs):
        for sample_entry in batch_entry['per_interesting_sample_stats']:
            for gen_entry in sample_entry.get('per_generalization_stats', []):
                gen_id = gen_entry['id']
                ab_path = base_dir / 'discoveries' / f'{gen_id}.json'
                if not ab_path.exists():
                    continue
                absblock = load_json_config(ab_path)
                clear_doc_entries(absblock)
                num_insns = len(absblock['ab']['abs_insns'])
                witness_len = gen_entry['witness_len']

                ab_metrics = metrics_dict.get(gen_id, None)
                if ab_metrics is not None:
                    mean_interestingness = ab_metrics['mean_interestingness']
                    ab_coverage = ab_metrics['ab_coverage']
                else:
                    mean_interestingness = 42.0
                    ab_coverage = 42.0

                discovery_objs.append(Discovery(
                        batch = batch_obj,
                        identifier = gen_id,
                        absblock = absblock,
                        num_insns = num_insns,
                        witness_len = witness_len,
                        interestingness = mean_interestingness,
                        ab_coverage = ab_coverage,
                    ))
    Discovery.objects.bulk_create(discovery_objs)

    if len(metrics_dict) > 0:
        # We need to retrieve the bulk-inserted objects with an additional query,
        # since most db backends do not provide the ids of bulk-inserted objects.
        # Nevertheless, this is a lot faster than creating each discovery object
        # individually.
        discovery_objs = Discovery.objects.filter(batch__campaign=campaign)
        measurement_objs = []
        for discovery_obj in discovery_objs:
            ab_metrics = metrics_dict.get(discovery_obj.identifier, None)
            if ab_metrics is not None:
                for interestingness in ab_metrics['interestingness_series']:
                    measurement_objs.append(Measurement(discovery=discovery_obj, interestingness=interestingness))
        Measurement.objects.bulk_create(measurement_objs)


def clear_doc_entries(json_dict):
    if isinstance(json_dict, dict):
        for k in list(json_dict.keys()):
            if k.endswith('.doc'):
                del json_dict[k]
            else:
                clear_doc_entries(json_dict[k])
    elif isinstance(json_dict, list) or isinstance(json_dict, tuple):
        for i in json_dict:
            clear_doc_entries(i)

