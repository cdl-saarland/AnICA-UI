from django.db import models

# Create your models here.

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
    num_sampled = models.IntegerField()
    num_interesting = models.IntegerField()

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
    occuring_insnschemes = models.ManyToManyField(InsnScheme)

    def __str__(self):
        return self.identifier


class Witness(models.Model):
    discovery = models.OneToOneField(Discovery, on_delete=models.CASCADE)


from pathlib import Path

from django.utils.dateparse import parse_datetime

from devidisc.configurable import load_json_config


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

    for batch_entry in report['per_batch_stats']:
        num_sampled = batch_entry['num_sampled']
        num_interesting = batch_entry['num_interesting']
        batch_obj = campaign.discoverybatch_set.create(num_sampled=num_sampled, num_interesting=num_interesting)
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
                batch_obj.discovery_set.create(
                        identifier = gen_id,
                        absblock = absblock,
                        num_insns = num_insns,
                        witness_len = witness_len,
                        interestingness = 42.0,
                    )

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

