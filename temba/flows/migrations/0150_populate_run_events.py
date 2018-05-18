# Generated by Django 1.11.6 on 2018-03-23 16:11

import six
import time
import os

from datetime import timedelta
from django.db import migrations, transaction
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.text import force_text
from django_redis import get_redis_connection
from six.moves import range
from temba.utils import chunk_list
from uuid import uuid4

CACHE_KEY_HIGHPOINT = 'events_mig_highpoint'
CACHE_KEY_MAX_RUN_ID = 'events_mig_max_run_id'
CACHE_KEY_ACTIONSET_EXITS = 'events_mig_exit_uuids'

PATH_STEP_UUID = 'uuid'
PATH_NODE_UUID = 'node_uuid'
PATH_ARRIVED_ON = 'arrived_on'
PATH_EXIT_UUID = 'exit_uuid'
PATH_MAX_STEPS = 100

ONE_WEEK = 60 * 60 * 24 * 7


def translate(translations, preferred_langs):
    if translations is None:
        return None
    if isinstance(translations, six.string_types):
        return translations

    for lang in preferred_langs:
        if lang in translations:
            return translations[lang]

    return six.next(six.itervalues(translations))


def serialize_message(msg):
    serialized = {'text': msg.text}

    if msg.uuid:
        serialized['uuid'] = str(msg.uuid)
    if msg.contact_urn_id:
        serialized['urn'] = msg.contact_urn.identity
    if msg.channel_id:
        serialized['channel'] = {'uuid': str(msg.channel.uuid), 'name': msg.channel.name}
    if msg.attachments:
        serialized['attachments'] = msg.attachments

    return serialized


def serialize_broadcast(bcast, flow, contact):
    preferred_langs = []
    if contact.language:
        preferred_langs.append(contact.language)
    preferred_langs.append(flow.base_language)

    serialized = {'text': translate(bcast.text, preferred_langs)}

    if bcast.media:
        serialized['attachments'] = [translate(bcast.media, preferred_langs)]

    return serialized


def exit_uuid_for_step(step, prev_used, action_set_objs, cache):
    if step.step_type == 'R':
        return step.rule_uuid

    exit_uuid = prev_used.get(step.step_uuid)
    if exit_uuid:
        return exit_uuid

    exit_uuid = action_set_objs.get(step.step_uuid)
    if exit_uuid:
        return exit_uuid

    exit_uuid = cache.hget(CACHE_KEY_ACTIONSET_EXITS, step.step_uuid)
    if exit_uuid:
        return force_text(exit_uuid)

    exit_uuid = str(uuid4())
    cache.hset(CACHE_KEY_ACTIONSET_EXITS, step.step_uuid, exit_uuid)
    cache.expire(CACHE_KEY_ACTIONSET_EXITS, ONE_WEEK)
    return exit_uuid


def fill_path_and_events(run, action_set_uuid_to_exit, cache):
    steps = list(run.steps.all())

    # there was a period of time when we deleted steps when a flow was deleted. In this case we just fill the existing
    # path with step UUIDs for consistency and move on
    if not steps:
        for path_step in run.path:
            if PATH_STEP_UUID not in path_step:
                path_step[PATH_STEP_UUID] = str(uuid4())
        run.save(update_fields=('path',))
        return

    # if we have steps, we rebuild the JSON path as these aren't 100% right sometimes for surveyor runs, due to
    # a previous migration sorting steps by arrived_on, and surveyor steps often having same arrived_on values

    old_path = run.path
    old_events = run.events

    # we can re-use exit_uuids calculated in previous migration for actionsets which always have the same exit_uuid
    previous_exit_uuids = {s[PATH_NODE_UUID]: s.get(PATH_EXIT_UUID) for s in run.path if s.get(PATH_EXIT_UUID)}

    run.path = []
    run.events = []
    seen_msgs = set()

    for step in steps:
        path_step = {
            PATH_STEP_UUID: str(uuid4()),
            PATH_NODE_UUID: step.step_uuid,
            PATH_ARRIVED_ON: step.arrived_on.isoformat(),
        }
        if step.left_on:
            exit_uuid = exit_uuid_for_step(step, previous_exit_uuids, action_set_uuid_to_exit, cache)
            path_step[PATH_EXIT_UUID] = exit_uuid

        run.path.append(path_step)

        step_events = []

        # generate message events for this step
        for msg in step.messages.all():
            if msg not in seen_msgs:
                seen_msgs.add(msg)
                step_events.append({
                    'type': 'msg_received' if msg.direction == 'I' else 'msg_created',
                    'created_on': msg.created_on.isoformat(),
                    'step_uuid': path_step[PATH_STEP_UUID],
                    'msg': serialize_message(msg)
                })

        for bcast in step.broadcasts.all():
            step_events.append({
                'type': 'msg_created',
                'created_on': bcast.created_on.isoformat(),
                'step_uuid': path_step[PATH_STEP_UUID],
                'msg': serialize_broadcast(bcast, run.flow, run.contact)
            })

        for evt in sorted(step_events, key=lambda e: e['created_on']):
            run.events.append(evt)

    # trim final path if necessary
    if len(run.path) > PATH_MAX_STEPS:
        run.path = run.path[len(run.path) - PATH_MAX_STEPS:]

    if old_path != run.path or old_events != run.events:
        run.save(update_fields=('events', 'path'))


def backfill_flowrun_events(FlowRun, Flow, ActionSet, Contact, FlowStep, Msg, Channel, ContactURN, Broadcast):
    cache = get_redis_connection()

    # get all flow action sets
    action_sets = list(ActionSet.objects.filter(flow__is_active=True))
    if not action_sets:
        return

    print("Found %d flow action sets..." % len(action_sets))

    # make map of action set node UUIDs to their exit UUIDs
    action_set_uuid_to_exit = {a.uuid: a.exit_uuid for a in action_sets if a.exit_uuid}

    if len(action_sets) != len(action_set_uuid_to_exit):
        raise ValueError(
            "Found actionsets without exit_uuids, use migrate_flows command to migrate these flows forward"
        )

    # are we running on just a partition of the runs?
    partition = os.environ.get('PARTITION')
    if partition is not None:
        partition = int(partition)
        if partition < 0 or partition > 3:
            raise ValueError("Partition must be 0-3")

        print("Migrating runs in partition %d" % partition)

    # has this migration been run before but didn't complete?
    highpoint = None
    if partition is not None:
        highpoint = cache.get(CACHE_KEY_HIGHPOINT + (':%d' % partition))
    if highpoint is None:
        highpoint = cache.get(CACHE_KEY_HIGHPOINT)

    highpoint = 0 if highpoint is None else int(highpoint)

    max_run_id = cache.get(CACHE_KEY_MAX_RUN_ID)
    if max_run_id is None:
        max_run = FlowRun.objects.order_by('-id').first()
        if max_run:
            max_run_id = max_run.id
            cache.set(CACHE_KEY_MAX_RUN_ID, max_run_id, ONE_WEEK)
        else:
            return  # no work to do here
    else:
        max_run_id = int(max_run_id)

    if highpoint:
        print("Resuming from previous highpoint at run #%d" % highpoint)

    if max_run_id:
        print("Migrating runs up to run #%d" % max_run_id)

    remaining_estimate = (max_run_id - highpoint) // 4 if partition is not None else (max_run_id - highpoint)
    print("Estimated %d runs need to be migrated" % remaining_estimate)

    num_updated = 0
    start = time.time()

    # we want to prefetch flow, contact and steps with each flow run
    flow_prefetch = Prefetch('flow', queryset=Flow.objects.only('id', 'base_language'))
    contact_prefetch = Prefetch('contact', queryset=Contact.objects.only('id', 'language'))
    steps_prefetch = Prefetch('steps', queryset=FlowStep.objects.order_by('id'))
    messages_prefetch = Prefetch('steps__messages', queryset=Msg.objects.defer('metadata').order_by('created_on'))
    messages_channel_prefetch = Prefetch('steps__messages__channel', queryset=Channel.objects.only('id', 'name', 'uuid'))
    messages_urn_prefetch = Prefetch('steps__messages__contact_urn', queryset=ContactURN.objects.only('id', 'identity'))
    broadcasts_prefetch = Prefetch('steps__broadcasts', queryset=Broadcast.objects.defer('metadata').filter(purged=True).order_by('created_on'))

    for run_id_batch in chunk_list(range(highpoint, max_run_id + 1), 4000):
        with transaction.atomic():
            if partition is not None:
                run_id_batch = [r_id for r_id in run_id_batch if ((r_id + partition) % 4 == 0)]

            batch = (
                FlowRun.objects
                .filter(id__in=run_id_batch)
                .defer('results', 'fields')
                .prefetch_related(
                    flow_prefetch,
                    contact_prefetch,
                    steps_prefetch,
                    messages_prefetch,
                    messages_channel_prefetch,
                    messages_urn_prefetch,
                    broadcasts_prefetch,
                )
                .order_by('id')
            )

            for run in batch:
                fill_path_and_events(run, action_set_uuid_to_exit, cache)

                highpoint = run.id
                if partition is not None:
                    cache.set(CACHE_KEY_HIGHPOINT + (":%d" % partition), str(run.id), ONE_WEEK)
                else:
                    cache.set(CACHE_KEY_HIGHPOINT, str(run.id), ONE_WEEK)

        num_updated += len(run_id_batch)
        updated_per_sec = num_updated / (time.time() - start)

        # figure out estimated time remaining
        num_remaining = ((max_run_id - highpoint) // 4) if partition is not None else (max_run_id - highpoint)
        time_remaining = (num_remaining / updated_per_sec) if updated_per_sec > 0 else 0
        finishes = timezone.now() + timedelta(seconds=time_remaining)
        status = " > Updated %d runs of ~%d (%2.2f per sec) Est finish: %s" % (num_updated, remaining_estimate, updated_per_sec, finishes)

        if partition is not None:
            status += ' [PARTITION %d]' % partition

        print(status)

    print("Run events migration completed in %d mins" % (int(time.time() - start) // 60))


def apply_manual():
    from temba.channels.models import Channel
    from temba.contacts.models import Contact, ContactURN
    from temba.flows.models import Flow, ActionSet, FlowRun, FlowStep
    from temba.msgs.models import Msg, Broadcast

    backfill_flowrun_events(FlowRun, Flow, ActionSet, Contact, FlowStep, Msg, Channel, ContactURN, Broadcast)


def apply_as_migration(apps, schema_editor):
    FlowRun = apps.get_model('flows', 'FlowRun')
    Flow = apps.get_model('flows', 'Flow')
    ActionSet = apps.get_model('flows', 'ActionSet')
    Contact = apps.get_model('contacts', 'Contact')
    FlowStep = apps.get_model('flows', 'FlowStep')
    Msg = apps.get_model('msgs', 'Msg')
    Channel = apps.get_model('channels', 'Channel')
    ContactURN = apps.get_model('contacts', 'ContactURN')
    Broadcast = apps.get_model('msgs', 'Broadcast')

    backfill_flowrun_events(FlowRun, Flow, ActionSet, Contact, FlowStep, Msg, Channel, ContactURN, Broadcast)


def clear_migration(apps, schema_editor):
    r = get_redis_connection()
    r.delete('events_mig_max_run_id')
    r.delete('events_mig_highpoint')
    r.delete('events_mig_highpoint:0')
    r.delete('events_mig_highpoint:1')
    r.delete('events_mig_highpoint:2')
    r.delete('events_mig_highpoint:3')


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0149_update_path_trigger'),
    ]

    operations = [
        migrations.RunPython(apply_as_migration, clear_migration)
    ]
