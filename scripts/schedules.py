"""Create, list, and inspect local weekly schedules."""

import argparse

from scripts._common import add_database_option, database_service, print_summary, report_error
from src.domain.periods import WEEKDAYS


def main(argv: list[str] | None = None) -> int:
    """Run schedule creation and read-only inspection commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_database_option(parser)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create a named typical week")
    create.add_argument("name")
    add_employee = commands.add_parser("add-employee", help="add a worker and weekly hour limit")
    add_employee.add_argument("schedule_id", type=int)
    add_employee.add_argument("name")
    add_employee.add_argument("weekly_max_hours", type=int)
    commands.add_parser("list", help="list schedule IDs and names")
    show = commands.add_parser("show", help="inspect one schedule")
    show.add_argument("schedule_id", type=int)
    show.add_argument("--demand", action="store_true", help="print all 112 hourly demand rows")
    show.add_argument("--history", action="store_true", help="list prior-state snapshots")
    args = parser.parse_args(argv)
    try:
        service = database_service(args.db_name, must_exist=args.command != "create")
        if args.command == "create":
            schedule = service.create_schedule(args.name)
            print(f"Created schedule ID {schedule.id}: {schedule.name}")
        elif args.command == "add-employee":
            result = service.add_employee(args.schedule_id, args.name, args.weekly_max_hours)
            print(
                f"Added employee {result.state.employees[-1].id}: {result.state.employees[-1].name}"
            )
        elif args.command == "list":
            schedules = service.list_schedules()
            for schedule in schedules:
                print(f"ID {schedule.id}: {schedule.name}")
            if not schedules:
                print("No schedules yet")
        else:
            result = service.get_schedule(args.schedule_id)
            print_summary(result)
            print(
                f"Threshold: {result.state.threshold}; daily shift limit: {result.state.daily_shift_limit}"
            )
            for shift in result.state.shifts:
                print(f"Shift {shift.id}: {shift.start_hour:02d}:00-{shift.end_hour:02d}:00")
            for employee in result.employees:
                print(
                    f"Employee {employee.employee_id}: {employee.name}, {employee.assigned_hours}/{employee.maximum_hours} hours"
                )
            for assignment in result.state.assignments:
                print(
                    f"Assignment {assignment.id}: {WEEKDAYS[assignment.day]}, employee {assignment.employee_id}, shift {assignment.shift_id}"
                )
            if args.demand:
                for hour in result.hourly:
                    if hour.transactions is not None:
                        print(
                            f"{WEEKDAYS[hour.day]} {hour.hour:02d}:00 transactions={hour.transactions} required={hour.required} scheduled={hour.scheduled}"
                        )
            if args.history:
                for snapshot in service.list_snapshots(args.schedule_id):
                    print(
                        f"Snapshot {snapshot.id}: {snapshot.reason}, {snapshot.captured_at_utc}, prior version {snapshot.prior_version}"
                    )
    except (ValueError, OSError) as error:
        return report_error(error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
