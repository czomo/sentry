from __future__ import absolute_import

import logging

from django import forms

from sentry.rules.actions.base import IntegrationEventAction

logger = logging.getLogger("sentry.rules")

# TODO instead of hard-coding things, lets automatically select the first integration.
HARDCODED_ISSUE_TYPES = [
    ("Bug", "Bug"),
    ("Issue", "Issue"),
    ("Task", "Task"),
]


class JiraNotifyServiceForm(forms.Form):
    jira_project = forms.ChoiceField(choices=(), widget=forms.Select())
    issue_type = forms.ChoiceField(choices=(), widget=forms.Select())

    def __init__(self, *args, **kwargs):
        projects_list = [(i.id, i.name) for i in kwargs.pop("integrations")]
        super(JiraNotifyServiceForm, self).__init__(*args, **kwargs)

        if projects_list:
            self.fields["jira_project"].initial = projects_list[0][0]

        self.fields["jira_project"].choices = projects_list
        self.fields["jira_project"].widget.choices = self.fields["jira_project"].choices

    def clean(self):
        """
        TODO DESCRIBE
        :return:
        """

        channel_id = None
        if self.data.get("input_channel_id"):
            logger.info(
                "rule.slack.provide_channel_id",
                extra={
                    "slack_integration_id": self.data.get("workspace"),
                    "channel_id": self.data.get("channel_id"),
                },
            )
            # default to "#" if they have the channel name without the prefix
            channel_prefix = self.data["channel"][0] if self.data["channel"][0] == "@" else "#"
            channel_id = self.data["input_channel_id"]

        cleaned_data = super(JiraNotifyServiceForm, self).clean()

        workspace = cleaned_data.get("workspace")
        try:
            integration = Integration.objects.get(id=workspace)
        except Integration.DoesNotExist:
            raise forms.ValidationError(
                _("Slack workspace is a required field.", ), code="invalid",
            )

        channel = cleaned_data.get("channel", "")

        # XXX(meredith): If the user is creating/updating a rule via the API and provides
        # the channel_id in the request, we don't need to call the channel_transformer - we
        # are assuming that they passed in the correct channel_id for the channel
        if not channel_id:
            try:
                channel_prefix, channel_id, timed_out = self.channel_transformer(
                    integration, channel
                )
            except DuplicateDisplayNameError as e:
                domain = integration.metadata["domain_name"]

                params = {"channel": e.message, "domain": domain}

                raise forms.ValidationError(
                    _(
                        'Multiple users were found with display name "%(channel)s". Please use your username, found at %(domain)s/account/settings.',
                    ),
                    code="invalid",
                    params=params,
                )

        channel = strip_channel_name(channel)

        if channel_id is None and timed_out:
            cleaned_data["channel"] = channel_prefix + channel
            self._pending_save = True
            return cleaned_data

        if channel_id is None and workspace is not None:
            params = {
                "channel": channel,
                "workspace": dict(self.fields["workspace"].choices).get(int(workspace)),
            }

            raise forms.ValidationError(
                _(
                    'The slack resource "%(channel)s" does not exist or has not been granted access in the %(workspace)s Slack workspace.'
                ),
                code="invalid",
                params=params,
            )

        cleaned_data["channel"] = channel_prefix + channel
        cleaned_data["channel_id"] = channel_id

        return cleaned_data


class JiraCreateTicketAction(IntegrationEventAction):
    form_cls = JiraNotifyServiceForm
    label = u"Create a {issue_type} in the {jira_project} Jira project"
    prompt = "Create a Jira ticket"
    provider = "jira"
    integration_key = "jira_project"

    def __init__(self, *args, **kwargs):
        super(JiraCreateTicketAction, self).__init__(*args, **kwargs)
        # TODO 1.1 Add form_fields
        # TODO 2.0 what if there are multiple Jira integrations?

        # TODO MARCOS we need to know which integration to populate the other fields
        # TODO MARCOS it'll help to have the MOCKS DONE FOR THIS

        # TODO is this already cached?

        all_integrations = self.get_integrations()
        integration_choices = [(i.id, i.name) for i in all_integrations]

        self.form_fields = {
            "jira_integration": {
                "type": "choice",
                "choices": integration_choices,
                "default": integration_choices[0][0],
                "updatesForm": True,
            },
            "jira_project": {
                "type": "choice",
                "choices": integration_choices,
                "default": integration_choices[0][0],
                "updatesForm": True,
            },
            "issue_type": {
                "type": "choice",
                "choices": HARDCODED_ISSUE_TYPES,
                "default": HARDCODED_ISSUE_TYPES[0][0],
            },
        }

    def render_label(self):
        return self.label.format(jira_project=self.get_integration_name(), issue_type="asdf")

    def after(self, event, state):
        pass
