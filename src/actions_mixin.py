# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Actions mixin for BindCharm."""

# Ignore having too few public methods for a mixin
# pylint: disable=too-few-public-methods

import ops

import bind


class ActionsMixin:
    """Regroups actions of the BindCharm.

    Attributes:
        bind: attribute from BindCharm
        framework: attribute from BindCharm
        on: attribute from BindCharm
    """

    bind: bind.BindService
    framework: ops.Framework
    on: ops.CharmEvents

    def hooks(self) -> None:
        """Define hooks that BindCharm should observe."""
        # We ignore the type of the `self` argument of each hook
        # as mypy has trouble understanding it
        self.framework.observe(
            self.on.create_acl_action, self._on_create_acl_action  # type: ignore[arg-type]
        )
        self.framework.observe(
            self.on.delete_acl_action, self._on_delete_acl_action  # type: ignore[arg-type]
        )
        self.framework.observe(
            self.on.check_acl_action, self._on_check_acl_action  # type: ignore[arg-type]
        )
        self.framework.observe(
            self.on.list_acl_action, self._on_list_acl_action  # type: ignore[arg-type]
        )

    def _on_create_acl_action(self, event: ops.charm.ActionEvent) -> None:
        """Handle the create ACL ActionEvent.

        Args:
            event: Event triggering this action handler.
        """
        event.set_results(
            {
                "result": self.bind.command(
                    f"create_acl {event.params['service-account']} {event.params['zone']}"
                )
            }
        )

    def _on_delete_acl_action(self, event: ops.charm.ActionEvent) -> None:
        """Handle the create ACL ActionEvent.

        Args:
            event: Event triggering this action handler.
        """
        event.set_results(
            {
                "result": self.bind.command(
                    f"delete_acl {event.params['service-account']} {event.params['zone']}"
                )
            }
        )

    def _on_check_acl_action(self, event: ops.charm.ActionEvent) -> None:
        """Handle the create ACL ActionEvent.

        Args:
            event: Event triggering this action handler.
        """
        event.set_results(
            {
                "result": self.bind.command(
                    f"check_acl {event.params['service-account']} {event.params['zone']}"
                )
            }
        )

    def _on_list_acl_action(self, event: ops.charm.ActionEvent) -> None:
        """Handle the create ACL ActionEvent.

        Args:
            event: Event triggering this action handler.
        """
        event.set_results({"result": self.bind.command("list_acl")})
