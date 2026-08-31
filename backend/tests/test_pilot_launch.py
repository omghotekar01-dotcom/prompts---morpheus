from __future__ import annotations

import pytest

from app.pilot_launch import build_pilot_launch_plan


def test_default_pilot_launch_plan_is_deterministic_single_worker_loopback() -> None:
    first = build_pilot_launch_plan()
    second = build_pilot_launch_plan()
    assert first == second
    assert first.schema == "morpheus-pilot-launch-plan-v1"
    assert first.host == "127.0.0.1"
    assert first.port == 8000
    assert first.workers == 1
    assert first.loopback_only is True
    assert first.explicit_network_bind is False
    assert first.production_deployment_authorized is False
    assert len(first.sha256) == 64


def test_non_loopback_bind_fails_closed_without_explicit_acknowledgement() -> None:
    with pytest.raises(ValueError, match="non-loopback"):
        build_pilot_launch_plan(host="0.0.0.0")

    plan = build_pilot_launch_plan(host="0.0.0.0", allow_network_bind=True)
    assert plan.loopback_only is False
    assert plan.explicit_network_bind is True
    assert plan.workers == 1
    assert plan.production_deployment_authorized is False
    assert any("tls" in boundary.lower() for boundary in plan.truth_boundaries)


def test_ipv6_loopback_does_not_require_network_acknowledgement() -> None:
    plan = build_pilot_launch_plan(host="::1")
    assert plan.loopback_only is True
    assert plan.explicit_network_bind is False


def test_invalid_pilot_port_and_host_fail_closed() -> None:
    for port in (0, 65536, True):
        with pytest.raises(ValueError, match="port"):
            build_pilot_launch_plan(port=port)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="host"):
        build_pilot_launch_plan(host=" network-host ")
