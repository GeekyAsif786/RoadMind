from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from time import sleep
from uuid import uuid4

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models import (
    Intersection,
    SignalControlCommand,
    SignalControllerState,
    SignalPhase,
    SignalPlan,
)
from app.models.domain import DeviceCredential
from app.schemas import SignalControllerStateCreate
from app.services.signal_controller_state_service import (
    SignalControllerStateService,
)


def test_concurrent_execution_reports_are_serialized():
    intersection_id = uuid4()
    device_id = uuid4()
    plan_id = uuid4()
    command_id = uuid4()

    intersection_name = f"concurrency-test-{uuid4().hex}"

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=5)

    setup_db = SessionLocal()

    try:
        # --------------------------------------------------
        # 1. Create parent intersection first.
        # --------------------------------------------------

        intersection = Intersection(
            id=intersection_id,
            name=intersection_name,
            latitude=22.5726,
            longitude=88.3639,
            lanes=4,
            road_type="urban",
            status="active",
        )

        setup_db.add(intersection)
        setup_db.commit()

        # --------------------------------------------------
        # 2. Create records that depend on intersection.
        # --------------------------------------------------

        device = DeviceCredential(
            id=device_id,
            intersection_id=intersection_id,
            name=f"concurrency-device-{uuid4().hex}",
            credential_id=f"test_{uuid4().hex[:20]}",
            credential_hash="test-hash",
            scopes=[
                "signal:control",
                "signal:state:write",
            ],
            is_active=True,
        )

        plan = SignalPlan(
            id=plan_id,
            intersection_id=intersection_id,
            green_seconds=20,
            yellow_seconds=4,
            red_seconds=3,
            priority="normal",
            reason="Concurrency test",
            decision_source="test",
            expires_at=expires_at,
        )

        setup_db.add_all([device, plan])
        setup_db.commit()

        # --------------------------------------------------
        # 3. Create phase and command.
        # --------------------------------------------------

        phase = SignalPhase(
            id=uuid4(),
            plan_id=plan_id,
            phase_number=2,
            direction="N",
            green_seconds=20,
            yellow_seconds=4,
            phase_order=1,
        )

        command = SignalControlCommand(
            id=command_id,
            intersection_id=intersection_id,
            device_id=device_id,
            plan_id=plan_id,
            phase_number=2,
            status="acknowledged",
            requested_at=now,
            expires_at=expires_at,
            acknowledged_at=now,
            execution_reported_at=None,
        )

        setup_db.add_all([phase, command])
        setup_db.commit()

    finally:
        setup_db.close()

    payload = SignalControllerStateCreate(
        current_phase=2,
        phase_state="green",
        controller_status="online",
        reported_plan_id=plan_id,
        phase_started_at=now,
    )

    # Used to prove the first transaction acquired the row lock.
    first_lock_acquired = Event()

    # Used to prove the second transaction attempted to acquire it.
    second_attempted = Event()

    # Used to release the first transaction after the second
    # transaction is known to be waiting.
    release_first = Event()

    def report_from_first_session():
        db = SessionLocal()

        try:
            service = SignalControllerStateService(db)

            original_get_for_update = (
                service.commands.get_for_update
            )

            def locked_get_for_update(command_id):
                command = original_get_for_update(command_id)

                first_lock_acquired.set()

                if not second_attempted.wait(timeout=5):
                    raise RuntimeError(
                        "Second execution report did not attempt "
                        "to acquire the command lock"
                    )

                if not release_first.wait(timeout=5):
                    raise RuntimeError(
                        "Test did not release the first transaction"
                    )

                return command

            service.commands.get_for_update = locked_get_for_update

            return service.report_command_execution(
                command_id=command_id,
                device_id=device_id,
                intersection_id=intersection_id,
                payload=payload,
            )

        finally:
            db.close()

    def report_from_second_session():
        db = SessionLocal()

        try:
            service = SignalControllerStateService(db)

            original_get_for_update = (
                service.commands.get_for_update
            )

            def waiting_get_for_update(command_id):
                second_attempted.set()

                # This SELECT ... FOR UPDATE should block until
                # the first transaction commits.
                return original_get_for_update(command_id)

            service.commands.get_for_update = waiting_get_for_update

            return service.report_command_execution(
                command_id=command_id,
                device_id=device_id,
                intersection_id=intersection_id,
                payload=payload,
            )

        finally:
            db.close()

    executor = ThreadPoolExecutor(max_workers=2)

    try:
        # --------------------------------------------------
        # First request acquires the command row lock.
        # --------------------------------------------------

        first_future = executor.submit(
            report_from_first_session
        )

        assert first_lock_acquired.wait(timeout=5)

        # --------------------------------------------------
        # Second request attempts the same command.
        # --------------------------------------------------

        second_future = executor.submit(
            report_from_second_session
        )

        assert second_attempted.wait(timeout=5)

        # Give PostgreSQL time to demonstrate that the second
        # transaction is blocked by FOR UPDATE.
        sleep(0.2)

        assert not second_future.done(), (
            "Second execution report was not blocked by "
            "the command row lock"
        )

        # --------------------------------------------------
        # Release first transaction.
        # --------------------------------------------------

        release_first.set()

        first_result = first_future.result(timeout=5)
        second_result = second_future.result(timeout=5)

        assert first_result.intersection_id == intersection_id
        assert second_result.intersection_id == intersection_id

    finally:
        release_first.set()
        executor.shutdown(wait=True)

    # ------------------------------------------------------
    # Verify final database state.
    # ------------------------------------------------------

    verify_db = SessionLocal()

    try:
        command = verify_db.get(
            SignalControlCommand,
            command_id,
        )

        state = verify_db.get(
            SignalControllerState,
            intersection_id,
        )

        assert command is not None
        assert command.execution_reported_at is not None
        assert command.status == "acknowledged"

        assert state is not None
        assert state.current_phase == 2
        assert state.phase_state == "green"
        assert state.reported_plan_id == plan_id

    finally:
        # Delete children first, then parents.
        verify_db.execute(
            delete(SignalControllerState).where(
                SignalControllerState.intersection_id
                == intersection_id
            )
        )

        verify_db.execute(
            delete(SignalControlCommand).where(
                SignalControlCommand.id == command_id
            )
        )

        verify_db.execute(
            delete(SignalPhase).where(
                SignalPhase.plan_id == plan_id
            )
        )

        verify_db.execute(
            delete(SignalPlan).where(
                SignalPlan.id == plan_id
            )
        )

        verify_db.execute(
            delete(DeviceCredential).where(
                DeviceCredential.id == device_id
            )
        )

        verify_db.execute(
            delete(Intersection).where(
                Intersection.id == intersection_id
            )
        )

        verify_db.commit()
        verify_db.close()