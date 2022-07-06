from django.db import models
from django.utils.dateparse import parse_datetime

import csv
from collections import defaultdict
import json
import math
from pathlib import Path

from iwho.configurable import load_json_config
import iwho

import logging
logger = logging.getLogger(__name__)

from anica.abstractblock import AbstractBlock
from anica.abstractioncontext import AbstractionContext
from anica.interestingness import InterestingnessMetric
from anica.satsumption import check_subsumed
from anica.bbset_coverage import get_table_metrics

from .helpers import load_abstract_block

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
from add_metrics import add_metrics_for_campaign_dir

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


# Models for the basic block view
class BasicBlockSet(models.Model):
    identifier = models.CharField(max_length=256, unique=True)
    isa = models.CharField(max_length=256)
    has_data_for = models.ManyToManyField(Tool)

class BasicBlockEntry(models.Model):
    bbset = models.ForeignKey(BasicBlockSet, on_delete=models.CASCADE)
    asm_str = models.TextField()
    hex_str = models.TextField()
    measurement_results = models.JSONField()
    interesting_for = models.ManyToManyField(Campaign, related_name='interesting_bbs')

class BasicBlockMeasurement(models.Model):
    bb = models.ForeignKey(BasicBlockEntry, on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    result = models.FloatField()

class BasicBlockSetMetrics(models.Model):
    bbset = models.ForeignKey(BasicBlockSet, on_delete=models.CASCADE)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    num_bbs_interesting = models.IntegerField()
    percent_bbs_interesting = models.FloatField()
    num_interesting_bbs_covered = models.IntegerField()
    percent_interesting_bbs_covered = models.FloatField()
    num_interesting_bbs_covered_top10 = models.IntegerField()
    percent_interesting_bbs_covered_top10 = models.FloatField()


def import_basic_block_set(isa, identifier, csv_file):
    data = []
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        keys = set(reader.fieldnames)
        for line in reader:
            data.append(line)

    assert 'bb' in keys, "Trying to import basic blocks from a csv file without 'bb' field!"
    keys.discard('bb')

    iwho_ctx = iwho.get_context_by_name(isa)

    tool_objs = { tool_name: Tool.objects.get_or_create(full_name=tool_name, defaults={})[0] for tool_name in keys }

    bbset = BasicBlockSet(identifier=identifier, isa=isa)
    bbset.save()

    for k, obj in tool_objs.items():
        bbset.has_data_for.add(obj)

    bbentry_objs = []
    for line in data:
        hex_str = line['bb']
        asm_str = "\n".join(iwho_ctx.coder.hex2asm(hex_str))
        measurement_results = { k: float(v) for k, v in line.items() if k != 'bb'}
        bbentry_objs.append(BasicBlockEntry(
                bbset=bbset,
                asm_str=asm_str,
                hex_str=hex_str,
                measurement_results=measurement_results,
            ))
    BasicBlockEntry.objects.bulk_create(bbentry_objs)

    # obtain the created objects with proper IDs
    bbentry_objs = BasicBlockEntry.objects.filter(bbset=bbset)

    bbmeasurement_objs = []
    for line, bbentry_obj in zip(data, bbentry_objs):
        assert line['bb'] == bbentry_obj.hex_str

        for k in keys:
            bbmeasurement_objs.append(BasicBlockMeasurement(
                    bb=bbentry_obj,
                    tool=tool_objs[k],
                    result=float(line[k]),
                ))
    BasicBlockMeasurement.objects.bulk_create(bbmeasurement_objs)

    return bbset.id


def import_campaign(tag, campaign_dir):
    base_dir = Path(campaign_dir)

    if not (base_dir / 'metrics.json').exists():
        add_metrics_for_campaign_dir(campaign_dir)

    campaign_config = load_json_config(base_dir / "campaign_config.json")

    abstraction_config = campaign_config["abstraction_config"]
    tools = campaign_config['predictors']
    termination_condition = campaign_config['termination']

    restrict_to_supported_insns = campaign_config['restrict_to_supported_insns']

    report = load_json_config(base_dir / "report.json")

    date = parse_datetime(report['start_date'])
    total_seconds = report['seconds_passed']
    host_pc = report['host_pc']

    # The better way would probably be to move/copy the files into the django
    # app's working space and to make this path relative to a fixed base. This
    # here breaks if the imported campaign directories are deleted or moved
    # around.
    witness_path = str((base_dir / 'witnesses').resolve())

    # avoid duplicate imports (this exploits the above implementation choice)
    duplicate = Campaign.objects.filter(witness_path=witness_path)
    if duplicate.exists():
        print(f"skipping campaign {campaign_dir} because it has alreadyh been imported")
        return

    tool_objs = [Tool.objects.get_or_create(full_name=tool_name, defaults={})[0] for tool_name in tools]

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

    return campaign.id

def compute_bbset_coverage(campaign_id_seq, bbset_id_seq, heuristic=False):
    """ Compute metrics on how many basic blocks from the specified BBSets are
    covered by the specified Campaigns.
    Both parameters should be sequences of numerical identifiers of
    corresponding data model objects. Pass empty lists to consider all
    registered entities.
    """
    if len(campaign_id_seq) == 0:
        campaign_id_seq = [ x.id for x in Campaign.objects.all() ]

    if len(bbset_id_seq) == 0:
        bbset_id_seq = [ x.id for x in BasicBlockSet.objects.all() ]

    for bbset_id in bbset_id_seq:
        bbset = BasicBlockSet.objects.get(pk=bbset_id)

        # produce iwho basic blocks
        isa = bbset.isa
        iwho_ctx = iwho.get_context_by_name(isa)

        all_bbentries = list(bbset.basicblockentry_set.all())
        num_bbs = len(all_bbentries)
        # for caching parsing results
        parsed_bbs = dict()

        for campaign_id in campaign_id_seq:
            campaign = Campaign.objects.get(pk=campaign_id)
            config_dict = campaign.config_dict
            tools = campaign.tools.all()

            # avoid duplicate computations
            relevant_metrics = BasicBlockSetMetrics.objects.filter(bbset=bbset, campaign=campaign)
            relevant_interestingness = BasicBlockEntry.interesting_for.through.objects.filter(campaign_id=campaign_id, basicblockentry_id__bbset=bbset)
            data_present = relevant_metrics.exists() or relevant_interestingness.exists()
            if data_present:
                print(f"skipping (campaign {campaign_id}, bbset {bbset_id}) because metrics are already present")
                continue

            tools_without_measurements = tools.difference(bbset.has_data_for.all())
            if tools_without_measurements.count() > 0:
                print("skipping (campaign {}, bbset {}) because necessary measurements are not present for {}".format(
                    campaign_id, bbset_id, [t.full_name for t in tools_without_measurements]))
                continue

            print(f"computing coverage metrics for (campaign {campaign_id}, bbset {bbset_id})")

            tool_names = [ t.full_name for t in tools ]

            interestingness_config = config_dict.get('interestingness_metric', {})
            interestingness_metric = InterestingnessMetric(interestingness_config)

            interesting_bbs = []
            for bbidx, bbentry in enumerate(all_bbentries):
                eval_res = {t.full_name: {
                            'TP': bbentry.basicblockmeasurement_set.filter(tool=t).get().result
                        } for t in tools
                    }
                is_interesting = interestingness_metric.is_interesting(eval_res)
                if is_interesting:
                    # basic blocks are parsed on demand and cached
                    parsed_bb = parsed_bbs.get(bbidx, None)
                    if parsed_bb is None:
                        asm_str = bbentry.asm_str
                        insns = iwho_ctx.parse_validated_asm(asm_str)
                        parsed_bb = iwho_ctx.make_bb(insns)
                        # inject the db object for later reference
                        parsed_bb.dbobj = bbentry
                        parsed_bbs[bbidx] = parsed_bb

                    interesting_bbs.append(parsed_bb)
                    bbentry.interesting_for.add(campaign)

            relevant_discoveries = Discovery.objects.filter(batch__campaign=campaign).filter(subsumed_by=None)

            all_abs = []
            actx = None
            for d in relevant_discoveries:
                absblock = d.absblock
                ab = load_abstract_block(absblock, actx)
                if actx is None:
                    actx = ab.actx
                # inject the db object for later reference
                ab.dbobj = d
                all_abs.append(ab)

            all_abs.sort(key=lambda x: len(x.abs_insns))

            metrics = get_table_metrics(actx=actx, all_abs=all_abs, interesting_bbs=interesting_bbs, total_num_bbs=num_bbs, heuristic=heuristic)

            obj = BasicBlockSetMetrics(bbset=bbset, campaign=campaign, **metrics)
            obj.save()


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

