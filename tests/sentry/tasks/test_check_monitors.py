from __future__ import absolute_import, print_function

from datetime import timedelta
from django.utils import timezone

from sentry.models import Monitor, MonitorStatus, MonitorType
from sentry.testutils import TestCase
from sentry.tasks.check_monitors import check_monitors


class CheckMonitorsTest(TestCase):
    def test_missing_checkin(self):
        org = self.create_organization()
        project = self.create_project(organization=org)

        monitor = Monitor.objects.create(
            organization_id=org.id,
            project_id=project.id,
            next_checkin=timezone.now() - timedelta(minutes=1),
            type=MonitorType.CRON_JOB,
            config={'schedule': '* * * * *'},
        )

        check_monitors()

        assert Monitor.objects.filter(
            id=monitor.id,
            status=MonitorStatus.FAILING,
        ).exists()

    def test_not_missing_checkin(self):
        org = self.create_organization()
        project = self.create_project(organization=org)

        monitor = Monitor.objects.create(
            organization_id=org.id,
            project_id=project.id,
            next_checkin=timezone.now() + timedelta(minutes=1),
            type=MonitorType.CRON_JOB,
            config={'schedule': '* * * * *'},
        )

        check_monitors()

        assert Monitor.objects.filter(
            id=monitor.id,
            status=MonitorStatus.ACTIVE,
        ).exists()
