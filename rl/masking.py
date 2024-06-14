"""Pure dynamic action-mask logic shared by training and inference."""

from __future__ import annotations

import numpy as np

from rl.actions import (
    ActionCatalog,
    ControlOperation,
    ErrorKind,
    TransactionType,
    configuration_is_supported,
    frame_is_supported,
)
from rl.backends.base import CoverageSnapshot, ProtocolState


def compute_action_mask(catalog: ActionCatalog, snapshot: CoverageSnapshot) -> np.ndarray:
    """Return a boolean mask for actions legal in ``snapshot``.

    Intentional error-injection actions are legal stimulus.  Accidental illegal
    protocol transitions and unsupported parameter combinations are masked.
    """

    mask = np.zeros(len(catalog), dtype=np.bool_)
    state = snapshot.protocol_state
    for action in catalog:
        allowed = False
        if action.transaction_type is TransactionType.CONFIGURE:
            allowed = state is not ProtocolState.RUNNING and configuration_is_supported(
                action, snapshot.capabilities
            )
        elif action.transaction_type is TransactionType.FRAME:
            allowed = state is ProtocolState.RUNNING and frame_is_supported(
                action,
                snapshot.capabilities,
                snapshot.current_configuration,
            )
        elif action.transaction_type is TransactionType.CONTROL:
            if action.control is ControlOperation.RESET:
                allowed = True
            elif action.control is ControlOperation.START:
                allowed = state is ProtocolState.CONFIGURED
            elif action.control is ControlOperation.FLUSH:
                allowed = state is ProtocolState.RUNNING
            elif action.control is ControlOperation.STOP:
                allowed = state in {ProtocolState.CONFIGURED, ProtocolState.RUNNING}
        elif action.transaction_type is TransactionType.ERROR_INJECTION:
            if action.error_kind is ErrorKind.INVALID_CONFIG:
                allowed = state is not ProtocolState.RUNNING
            elif action.error_kind is ErrorKind.INVALID_INPUT:
                allowed = state is ProtocolState.RUNNING
            elif action.error_kind is ErrorKind.INVALID_CONTROL:
                allowed = True
            elif action.error_kind is ErrorKind.RESPONSE_TIMEOUT:
                allowed = state is ProtocolState.RUNNING
        elif action.transaction_type is TransactionType.IDLE:
            allowed = True
        mask[action.index] = allowed

    if not np.any(mask):  # Defensive guard for custom catalogs/backends.
        raise RuntimeError("action mask contains no legal action")
    return mask


def configuration_choice_mask(
    catalog: ActionCatalog,
    snapshot: CoverageSnapshot,
) -> np.ndarray:
    """Advertise supported configurations independently of current state."""

    mask = np.zeros(len(catalog), dtype=np.int8)
    for action in catalog:
        if action.transaction_type is TransactionType.CONFIGURE:
            mask[action.index] = int(configuration_is_supported(action, snapshot.capabilities))
    return mask


def legal_action_indexes(catalog: ActionCatalog, snapshot: CoverageSnapshot) -> tuple[int, ...]:
    return tuple(int(index) for index in np.flatnonzero(compute_action_mask(catalog, snapshot)))
