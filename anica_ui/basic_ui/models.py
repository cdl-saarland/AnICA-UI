from django.db import models
from django.utils.dateparse import parse_datetime

from collections import defaultdict
import json
import math
from pathlib import Path

from iwho.configurable import load_json_config

import logging
logger = logging.getLogger(__name__)

from anica.abstractblock import AbstractBlock
from anica.abstractioncontext import AbstractionContext

from .helpers import load_abstract_block

class Tool(models.Model):
    full_name = models.CharField(max_length=255)

    def __str__(self):
        return self.full_name

class Campaign(models.Model):
    tag = models.CharField(max_length=255)

    config_dict = models.JSONField()
    tools = models.ManyToManyField(Tool)
    termination_condition = models.JSONField()

    date = models.DateField()
    host_pc = models.CharField(max_length=255)
    total_seconds = models.IntegerField()

    restrict_to_supported_insns = models.BooleanField()

    witness_path = models.CharField(max_length=2048) # a path to the directory where we find the witness files.

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
    interestingness = models.FloatField(null=True)
    subsumed_by = models.CharField(max_length=63, null=True)
    generality = models.IntegerField()
    occurring_insnschemes = models.ManyToManyField(InsnScheme)
    remarks = models.TextField(null=True)

    def __str__(self):
        return self.identifier

class Measurement(models.Model):
    discovery = models.ForeignKey(Discovery, on_delete=models.CASCADE)
    interestingness = models.FloatField()


class Witness(models.Model):
    discovery = models.OneToOneField(Discovery, on_delete=models.CASCADE)


class Generalization(models.Model):
    absblock = models.JSONField()
    tools = models.ManyToManyField(Tool)
    witness_file = models.CharField(max_length=2048)
    witness_len = models.IntegerField()
    interestingness = models.FloatField(null=True)
    generality = models.IntegerField()
    remarks = models.TextField(null=True)
    identifier = models.CharField(max_length=256, null=True)
    num_insns = models.IntegerField()


def import_campaign(tag, campaign_dir):
    base_dir = Path(campaign_dir)

    campaign_config = load_json_config(base_dir / "campaign_config.json")

    abstraction_config = campaign_config["abstraction_config"]
    tools = campaign_config['predictors']
    termination_condition = campaign_config['termination']

    restrict_to_supported_insns = campaign_config['restrict_to_supported_insns']

    report = load_json_config(base_dir / "report.json")

    date = parse_datetime(report['start_date'])
    total_seconds = report['seconds_passed']
    host_pc = report['host_pc']

    tool_objs = [Tool.objects.get_or_create(full_name=tool_name, defaults={})[0] for tool_name in tools]

    # The better way would probably be to move/copy the files into the django
    # app's working space and to make this path relative to a fixed base. This
    # here breaks if the imported campaign directories are deleted or moved
    # around.
    witness_path = str((base_dir / 'witnesses').resolve())

    campaign = Campaign(
            tag = tag,
            config_dict = abstraction_config,
            termination_condition = termination_condition,
            date = date,
            host_pc = host_pc,
            total_seconds = total_seconds,
            restrict_to_supported_insns = restrict_to_supported_insns,
            witness_path = witness_path,
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

    ischeme_map = defaultdict(set)
    used_ischemes = set()

    # TODO make this work
    # if restrict_to_supported_insns:
    #     # respect the restriction to the supported instructions, so that the generality is computed correctly here
    #     rest_keys = tools
    # else:
    #     rest_keys = None
    #
    # actx = AbstractionContext(config=abstraction_config, restrict_to_insns_for=rest_keys)

    actx = None

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

                remarks = absblock.get('remarks', None)
                if remarks is None:
                    remark_text = None
                else:
                    remark_strs = []
                    for r in remarks:
                        if isinstance(r, str):
                            remark_str = r
                        else:
                            assert isinstance(r, tuple) or isinstance(r, list)
                            remark_str = r[0].format(*r[1:])
                        remark_strs.append("<li>{}</li>".format(remark_str))
                    remark_text = "\n".join(remark_strs)

                ab = load_abstract_block(absblock, actx)
                if actx is None:
                    actx = ab.actx

                generality = math.inf
                for ai in ab.abs_insns:
                    feasible_schemes = actx.insn_feature_manager.compute_feasible_schemes(ai.features)
                    generality = min(generality, len(feasible_schemes))
                    for istr in map(str, feasible_schemes):
                        used_ischemes.add(istr)
                        ischeme_map[gen_id].add(istr)

                ab_metrics = metrics_dict.get(gen_id, None)
                if ab_metrics is not None:
                    mean_interestingness = ab_metrics['mean_interestingness']
                    subsumed_by = ab_metrics['subsumed_by']
                else:
                    mean_interestingness = None
                    subsumed_by = None

                discovery_objs.append(Discovery(
                        batch = batch_obj,
                        identifier = gen_id,
                        absblock = absblock,
                        num_insns = num_insns,
                        witness_len = witness_len,
                        interestingness = mean_interestingness,
                        subsumed_by = subsumed_by,
                        generality = generality,
                        remarks = remark_text,
                    ))
    Discovery.objects.bulk_create(discovery_objs)

    existing_ischemes = set(map(lambda x: x.text, InsnScheme.objects.all()))
    required_ischemes = used_ischemes - existing_ischemes
    if len(required_ischemes) > 0:
        # make sure that the length of the text field is sufficient
        assert all(map(lambda x: len(x) <= 255, required_ischemes))
        InsnScheme.objects.bulk_create(list(map(lambda x: InsnScheme(text=x), required_ischemes)))

    ischeme_objs = InsnScheme.objects.all()
    istr2obj = { obj.text: obj for obj in ischeme_objs }

    # Discovery.occurring_insnschemes is a many-to-many relation. To fill such a
    # relation using bulk inserts (which are essential for performance), we
    # need to get a bit more creative: Many-to-many relationships in django are
    # backed by a `through` model, which we obtain here. This is just a normal
    # model, which we can fill in bulk.
    discovery2ischeme_cls = Discovery.occurring_insnschemes.through

    through_objs = []

    # We need to retrieve the bulk-inserted objects with an additional query,
    # since most db backends do not provide the ids of bulk-inserted objects.
    # Nevertheless, this is a lot faster than creating each discovery object
    # individually.
    discovery_objs = Discovery.objects.filter(batch__campaign=campaign)
    measurement_objs = []
    for discovery_obj in discovery_objs:
        ident = discovery_obj.identifier
        for istr in ischeme_map[ident]:
            insnscheme_obj = istr2obj[istr]
            through_objs.append(discovery2ischeme_cls(discovery=discovery_obj, insnscheme=insnscheme_obj))

        ab_metrics = metrics_dict.get(ident, None)
        if ab_metrics is not None:
            for interestingness in ab_metrics['interestingness_series']:
                measurement_objs.append(Measurement(discovery=discovery_obj, interestingness=interestingness))
    Measurement.objects.bulk_create(measurement_objs)
    discovery2ischeme_cls.objects.bulk_create(through_objs)


def import_generalization(gen_dir):
    base_dir = Path(gen_dir)

    infos = load_json_config(base_dir / "infos.json")

    # this is an optional entry that needs to be added manually, to refer to specific generalizations
    identifier = infos.get('identifier', None)

    witness_len = infos['witness_len']

    tools = infos['predictors']
    tool_objs = [Tool.objects.get_or_create(full_name=tool_name, defaults={})[0] for tool_name in tools]

    # The better way would probably be to move/copy the files into the django
    # app's working space and to make this path relative to a fixed base. This
    # here breaks if the imported campaign directories are deleted or moved
    # around.
    witness_file = str((base_dir / 'witness.json').resolve())

    ab_path = base_dir / 'discovery.json'
    absblock = load_json_config(ab_path)
    clear_doc_entries(absblock)

    remarks = absblock.get('remarks', None)
    if remarks is None:
        remark_text = None
    else:
        remark_strs = []
        for r in remarks:
            if isinstance(r, str):
                remark_str = r
            else:
                assert isinstance(r, tuple) or isinstance(r, list)
                remark_str = r[0].format(*r[1:])
            remark_strs.append("<li>{}</li>".format(remark_str))
        remark_text = "\n".join(remark_strs)


    ab = load_abstract_block(absblock, actx=None)
    actx = ab.actx

    generality = math.inf
    for ai in ab.abs_insns:
        feasible_schemes = actx.insn_feature_manager.compute_feasible_schemes(ai.features)
        generality = min(generality, len(feasible_schemes))

    num_insns = len(ab.abs_insns)

    generalization = Generalization(
            absblock = absblock,
            witness_file = witness_file,
            witness_len = witness_len,
            interestingness = None,
            generality = generality,
            remarks = remark_text,
            identifier = identifier,
            num_insns = num_insns,
        )

    generalization.save()

    for t in tool_objs:
        generalization.tools.add(t.id)


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

