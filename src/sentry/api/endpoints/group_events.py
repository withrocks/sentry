from __future__ import absolute_import

import six

from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework.response import Response

from sentry import quotas, tagstore
from sentry.api.base import DocSection, EnvironmentMixin
from sentry.api.bases import GroupEndpoint
from sentry.api.exceptions import ResourceDoesNotExist
from sentry.api.helpers.environments import get_environments
from sentry.api.serializers import serialize
from sentry.api.paginator import DateTimePaginator
from sentry.api.utils import get_date_range_from_params
from sentry.models import Event, Group
from sentry.search.utils import parse_query
from sentry.utils.apidocs import scenario, attach_scenarios
from sentry.search.utils import InvalidQuery


@scenario('ListAvailableSamples')
def list_available_samples_scenario(runner):
    group = Group.objects.filter(project=runner.default_project).first()
    runner.request(method='GET', path='/issues/%s/events/' % group.id)


class GroupEventsEndpoint(GroupEndpoint, EnvironmentMixin):
    doc_section = DocSection.EVENTS

    @attach_scenarios([list_available_samples_scenario])
    def get(self, request, group):
        """
        List an Issue's Events
        ``````````````````````

        This endpoint lists an issue's events.

        :pparam string issue_id: the ID of the issue to retrieve.
        :auth: required
        """

        def respond(queryset):
            return self.paginate(
                request=request,
                queryset=queryset,
                order_by='-datetime',
                on_results=lambda x: serialize(x, request.user),
                paginator_cls=DateTimePaginator,
            )

        events = Event.objects.filter(group_id=group.id)

        try:
            environments = get_environments(request, group.project.organization)
        except ResourceDoesNotExist:
            return respond(events.none())

        raw_query = request.GET.get('query')

        if raw_query:
            try:
                query_kwargs = parse_query([group.project], raw_query, request.user)
            except InvalidQuery as exc:
                return Response({'detail': six.text_type(exc)}, status=400)
            else:
                query = query_kwargs.pop('query', None)
                tags = query_kwargs.pop('tags', {})
        else:
            query = None
            tags = {}

        if environments:
            env_names = set(env.name for env in environments)
            if 'environment' in tags:
                # If a single environment was passed as part of the query, then
                # we'll just search for that individual environment in this
                # query, even if more are selected.

                if tags['environment'] not in env_names:
                    # An event can only be associated with a single
                    # environment, so if the environments associated with
                    # the request don't contain the environment provided as a
                    # tag lookup, the query cannot contain any valid results.
                    return respond(events.none())
            else:
                # XXX: Handle legacy backends here. Just store environment as a
                # single tag if we only have one so that we don't break existing
                # usage.
                tags['environment'] = list(env_names) if len(env_names) > 1 else env_names.pop()

        if query:
            q = Q(message__icontains=query)

            if len(query) == 32:
                q |= Q(event_id__exact=query)

            events = events.filter(q)

        start, end = get_date_range_from_params(request.GET, optional=True)

        # TODO currently snuba can be used to get this filter of event_ids matching
        # the search tags, which is then used to further filter a postgres QuerySet
        # Ideally we would just use snuba to completely replace the fetching of the
        # events.
        if tags:
            event_filter = tagstore.get_group_event_filter(
                group.project_id,
                group.id,
                [env.id for env in environments],
                tags,
                start,
                end,
            )

            if not event_filter:
                return respond(events.none())

            events = events.filter(**event_filter)

        # Filter start/end here in case we didn't filter by tags at all
        if start:
            events = events.filter(datetime__gte=start)
        if end:
            events = events.filter(datetime__lte=end)

        # filter out events which are beyond the retention period
        retention = quotas.get_event_retention(organization=group.project.organization)
        if retention:
            events = events.filter(
                datetime__gte=timezone.now() - timedelta(days=retention)
            )

        return respond(events)
