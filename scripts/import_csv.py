"""Import or preview replacement of a bounded transaction CSV report."""

import argparse

from scripts._common import (
    add_database_option,
    database_service,
    print_summary,
    read_csv,
    report_error,
)


def main(argv: list[str] | None = None) -> int:
    """Import first demand or confirm a previewed replacement."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_database_option(parser)
    parser.add_argument("schedule_id", type=int)
    parser.add_argument("csv", help="CSV file inside data/")
    parser.add_argument(
        "--confirm-replace",
        action="store_true",
        help="commit a valid re-import and replace the roster",
    )
    args = parser.parse_args(argv)
    try:
        service = database_service(args.db_name, must_exist=True)
        report = read_csv(args.csv)
        current = service.get_schedule(args.schedule_id)
        if current.state.demand is None:
            result = service.import_initial(args.schedule_id, report)
            print("Initial demand imported; roster remains unchanged")
        else:
            preview = service.preview_refresh(args.schedule_id, csv_bytes=report)
            print(
                f"Replacement preview: {preview.removed_assignments} current, {preview.added_assignments} proposed assignments"
            )
            if not args.confirm_replace:
                print("Preview only; rerun with --confirm-replace to commit")
                print_summary(preview.draft)
                return 0
            result = service.confirm_refresh(
                args.schedule_id, preview.token, csv_bytes=report, confirmed=True
            )
            print("Demand replaced; prior state saved as a snapshot")
        print_summary(result)
    except (ValueError, OSError) as error:
        return report_error(error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
