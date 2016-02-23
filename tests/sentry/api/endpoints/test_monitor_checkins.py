from __future__ import absolute_import, print_function

from datetime import timedelta
from django.utils import timezone

from sentry.models import CheckInStatus, Monitor, MonitorCheckIn, MonitorStatus, MonitorType
from sentry.testutils import APITestCase


class CreateMonitorCheckInTest(APITestCase):
    def test_passing(self):
        user = self.create_user()
        org = self.create_organization(owner=user)
        project = self.create_project(organization=org)

        monitor = Monitor.objects.create(
            organization_id=org.id,
            project_id=project.id,
            next_checkin=timezone.now() - timedelta(minutes=1),
            type=MonitorType.CRON_JOB,
            config={'schedule': '* * * * *'},
        )

        self.login_as(user=user)
        with self.feature({'organizations:monitors': True}):
            resp = self.client.post('/monitors/{}/checkins/'.format(monitor.guid), data={
                'status': 'success'
            })

        assert resp.status_code == 200

        checkin = MonitorCheckIn.objects.get(guid=resp.data['id'])
        assert checkin.status == CheckInStatus.SUCCESS

        monitor = Monitor.objects.get(id=monitor.id)
        assert monitor.next_checkin == monitor.get_next_scheduled_checkin(checkin.date_added)
        assert monitor.status == MonitorStatus.ACTIVE
        assert monitor.last_checkin == checkin.date_addded

    def test_failing(self):
        user = self.create_user()
        org = self.create_organization(owner=user)
        project = self.create_project(organization=org)

        monitor = Monitor.objects.create(
            organization_id=org.id,
            project_id=project.id,
            next_checkin=timezone.now() - timedelta(minutes=1),
            type=MonitorType.CRON_JOB,
            config={'schedule': '* * * * *'},
        )

        self.login_as(user=user)
        with self.feature({'organizations:monitors': True}):
            resp = self.client.post('/monitors/{}/checkins/'.format(monitor.guid), data={
                'status': 'failure'
            })

        assert resp.status_code == 200

        checkin = MonitorCheckIn.objects.get(guid=resp.data['id'])
        assert checkin.status == CheckInStatus.FAILURE

        monitor = Monitor.objects.get(id=monitor.id)
        assert monitor.next_checkin == monitor.get_next_scheduled_checkin(checkin.date_added)
        assert monitor.status == MonitorStatus.FAILING
        assert monitor.last_checkin == checkin.date_addded
