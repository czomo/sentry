from __future__ import absolute_import

import responses

from sentry.integrations.jira import JiraCreateTicketAction
from sentry.models import Integration
from sentry.testutils.cases import RugleTestCase
from sentry.utils import json

# external_id is the account name in pagerduty
EXTERNAL_ID = "example-jira"


class MockJira:
    projects = {}

    def __init__(self):
        pass

    def create_ticket(self):
        pass

    def get_create_meta(self):
        return {}


# TODO MARCOS duplicate everything for azure devops.
class JiraCreateTicketActionTest(RuleTestCase):
    rule_cls = JiraCreateTicketAction

    def setUp(self):
        self.integration = Integration.objects.create(
            provider="jira",
            name="Example",
            external_id=EXTERNAL_ID,
            metadata={
                # TODO MARCOS
            },
        )
        self.integration.add_organization(self.organization, self.user)
        self.installation = self.integration.get_installation(self.organization.id)

    @responses.activate
    def test_applies_correctly(self):
        event = self.get_event()

        rule = self.get_rule(data={"account": self.integration.id})

        results = list(rule.after(event=event, state=self.get_state()))
        assert len(results) == 1

        responses.add(
            method=responses.POST,
            url="https://events.pagerduty.com/v2/enqueue/",
            json={},
            status=202,
            content_type="application/json",
        )

        # Trigger rule callback
        results[0].callback(event, futures=[])
        data = json.loads(responses.calls[0].request.body)

        assert data["event_action"] == "trigger"

    # TODO MARCOS
    def test_render_label(self):
        rule = self.get_rule(data={"account": self.integration.id})

        assert (
            rule.render_label()
            == "Create a Jira ticket in the Example account and Example project of type Bug"
        )

    def test_render_label_without_integration(self):
        self.integration.delete()

        rule = self.get_rule(data={"account": self.integration.id})

        assert (
            rule.render_label()
            == "Create a Jira ticket in the [removed] account and [removed] project of type Bug"
        )

    @responses.activate
    def test_invalid_integration(self):
        rule = self.get_rule(data={"account": self.integration.id})

        form = rule.get_form_instance()
        assert form.is_valid()

    @responses.activate
    def test_invalid_project(self):
        rule = self.get_rule(data={"account": self.integration.id})

        form = rule.get_form_instance()
        assert form.is_valid()
