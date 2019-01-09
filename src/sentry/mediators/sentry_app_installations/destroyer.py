from __future__ import absolute_import

from sentry.mediators import Mediator, Param
from sentry.mediators.sentry_app_installations.installation_notifier import InstallationNotifier


class Destroyer(Mediator):
    install = Param('sentry.models.SentryAppInstallation')
    user = Param('sentry.models.User')

    def call(self):
        self._destroy_authorization()
        self._destroy_grant()
        self._destroy_installation()
        return self.install

    def _destroy_authorization(self):
        self.install.authorization.delete()

    def _destroy_grant(self):
        self.install.api_grant.delete()

    def _destroy_installation(self):
        InstallationNotifier.run(
            install=self.install,
            user=self.user,
        )
        self.install.delete()
